from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal, cast

from aptos_sdk.account_address import AccountAddress
from pydantic import BaseModel, ConfigDict, field_validator

from .._pagination import PaginatedResponse
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "KnownWithdrawCancelReason",
    "PendingWithdrawRequest",
    "WithdrawQueueEntry",
    "WithdrawQueueReader",
    "WithdrawQueueResponse",
    "WithdrawQueueStatus",
    "WithdrawQueueUpdate",
    "is_known_cancel_reason",
    "merge_withdraw_queue_entries",
]

WithdrawQueueStatus = Literal["Queued", "Processed", "Cancelled"]

KnownWithdrawCancelReason = Literal[
    "CancelledByUser",
    "InsufficientWithdrawableBalance",
    "DepositCheckFailed",
]

_KNOWN_CANCEL_REASONS: frozenset[str] = frozenset(
    ("CancelledByUser", "InsufficientWithdrawableBalance", "DepositCheckFailed")
)


def is_known_cancel_reason(reason: str) -> bool:
    """Return True when the cancel reason is one of the known enum values."""
    return reason in _KNOWN_CANCEL_REASONS


class PendingWithdrawRequest(BaseModel):
    """On-chain view shape (liveness-check fallback), raw chain units."""

    model_config = ConfigDict(populate_by_name=True)

    request_id: str
    user: str
    recipient: str
    # Move `Option<T>` decoded: `{"vec": [...]}` -> first element or None.
    market: str | None = None
    metadata: str
    fungible_amount: str
    created_at: str

    @field_validator("market", mode="before")
    @classmethod
    def _unwrap_option(cls, value: Any) -> Any:
        if isinstance(value, dict) and "vec" in value:
            vec = cast("list[Any]", value["vec"])
            return vec[0] if vec else None
        return cast("Any", value)


class WithdrawQueueEntry(BaseModel):
    """Indexed entry from the trading API (normalized amounts, all statuses)."""

    model_config = ConfigDict(populate_by_name=True)

    user: str
    recipient: str | None = None
    market: str | None = None
    fungible_amount: float
    processed_amount: float
    request_id: str
    status: WithdrawQueueStatus
    cancel_reason: str | None = None
    timestamp_ms: int
    queued_at_ms: int | None = None
    transaction_version: int


WithdrawQueueResponse = PaginatedResponse[WithdrawQueueEntry]


class WithdrawQueueUpdate(BaseModel):
    """WS payload shape (topic stripped by the ws layer before parsing)."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[WithdrawQueueEntry]


def merge_withdraw_queue_entries(
    *,
    existing: list[WithdrawQueueEntry],
    delta: list[WithdrawQueueEntry],
) -> list[WithdrawQueueEntry]:
    """Merge incremental WS deltas into an existing entry list.

    Matches by ``request_id``; applies a delta only when its
    ``transaction_version`` is strictly greater. Field-level merge preserves
    non-null ``recipient`` / ``market`` / ``queued_at_ms`` from existing entries.
    Returns a new list sorted by queue time descending.
    """
    grouped: dict[str, list[WithdrawQueueEntry]] = {}
    for entry in existing:
        grouped.setdefault(entry.request_id, []).append(entry)

    merged: dict[str, WithdrawQueueEntry] = {}
    for request_id, rows in grouped.items():
        best = rows[0]
        for row in rows[1:]:
            if row.transaction_version > best.transaction_version:
                best = row
        recipient = best.recipient
        market = best.market
        queued_at_ms = best.queued_at_ms
        for row in rows:
            if recipient is None and row.recipient is not None:
                recipient = row.recipient
            if market is None and row.market is not None:
                market = row.market
            if queued_at_ms is None and row.queued_at_ms is not None:
                queued_at_ms = row.queued_at_ms
        merged[request_id] = best.model_copy(
            update={"recipient": recipient, "market": market, "queued_at_ms": queued_at_ms}
        )

    for update in delta:
        prev = merged.get(update.request_id)
        if prev is None:
            merged[update.request_id] = update
            continue
        if update.transaction_version <= prev.transaction_version:
            continue
        if update.status == "Cancelled":
            cancel_reason = (
                update.cancel_reason
                if update.cancel_reason is not None
                else (prev.cancel_reason if prev.status == "Cancelled" else None)
            )
        else:
            cancel_reason = None
        merged[update.request_id] = update.model_copy(
            update={
                "recipient": update.recipient if update.recipient is not None else prev.recipient,
                "market": update.market if update.market is not None else prev.market,
                "queued_at_ms": (
                    update.queued_at_ms if update.queued_at_ms is not None else prev.queued_at_ms
                ),
                "cancel_reason": cancel_reason,
            }
        )

    def _queue_time(entry: WithdrawQueueEntry) -> int:
        if entry.queued_at_ms is not None:
            return entry.queued_at_ms
        return entry.timestamp_ms if entry.status == "Queued" else 0

    result = list(merged.values())
    result.sort(key=_queue_time, reverse=True)
    return result


class WithdrawQueueReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        status: WithdrawQueueStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> PaginatedResponse[WithdrawQueueEntry]:
        params: dict[str, str] = {"account": sub_addr}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if status is not None:
            params["status"] = status
        response, _, _ = await self.get_request(
            model=PaginatedResponse[WithdrawQueueEntry],
            url=f"{self.config.trading_http_url}/api/v1/withdraw_queue",
            params=params,
        )
        return response

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[WithdrawQueueUpdate], None] | Callable[[WithdrawQueueUpdate], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"withdraw_queue:{sub_addr}"
        return self.ws.subscribe(topic, WithdrawQueueUpdate, on_data)

    async def get_pending_withdrawals(
        self,
        user_addr: str | AccountAddress,
    ) -> list[PendingWithdrawRequest]:
        """Return currently-queued withdrawals from the on-chain view (fallback).

        Returns an empty list when the queue module/resource is not found.
        """
        normalized = (
            user_addr
            if isinstance(user_addr, AccountAddress)
            else AccountAddress.from_str(user_addr)
        )
        pkg = self.config.deployment.package
        try:
            result_bytes = await self.aptos.view(
                f"{pkg}::async_withdraw_queue::get_pending_withdrawals",
                [],
                [str(normalized)],
            )
            result: list[Any] = json.loads(result_bytes.decode("utf-8"))
            return [PendingWithdrawRequest.model_validate(item) for item in result[0]]
        except Exception as e:
            msg = str(e)
            if any(
                code in msg
                for code in ("module_not_found", "function_not_found", "resource_not_found")
            ):
                return []
            raise
