from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Literal, cast

from aptos_sdk.account_address import AccountAddress
from aptos_sdk.async_client import ApiError
from pydantic import BaseModel, ConfigDict, field_validator

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

_REQUEST_ID_RE = re.compile(r"^\d{1,20}$")

# Errors that mean "there is simply nothing queued here" rather than a genuine RPC failure.
# `resource_not_found` is included deliberately — see get_pending_withdrawals' docstring.
_EMPTY_QUEUE_ERROR_CODES = frozenset(
    ("module_not_found", "function_not_found", "resource_not_found")
)


def is_known_cancel_reason(reason: str) -> bool:
    """Whether a ``cancel_reason`` is one the SDK knows about (new reasons pass through as-is)."""
    return reason in _KNOWN_CANCEL_REASONS


def _validate_request_id(value: str) -> str:
    if not _REQUEST_ID_RE.match(value):
        raise ValueError("request_id must be a numeric string (u64)")
    return value


class PendingWithdrawRequest(BaseModel):
    """On-chain view response shape, used for liveness-check fallback polling.

    This is *not* the primary data source — use :class:`WithdrawQueueEntry` from the indexed
    HTTP/WS API instead. The on-chain view only returns currently-Queued items and reports raw
    chain units (not normalized amounts). Use ``request_id`` to correlate the two.
    """

    model_config = ConfigDict(populate_by_name=True)

    request_id: str
    user: str
    recipient: str
    #: Move ``Option<T>`` decoded: ``None`` when the withdrawal is not market-specific.
    market: str | None = None
    metadata: str
    #: Raw chain units (u64 as string). Divide by ``10^collateral_decimals`` for display — this is
    #: NOT comparable to :attr:`WithdrawQueueEntry.fungible_amount`, which is already normalized.
    fungible_amount: str
    created_at: str

    _check_request_id = field_validator("request_id")(_validate_request_id)

    @field_validator("market", mode="before")
    @classmethod
    def _unwrap_option(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        option = cast("dict[str, Any]", value)
        vec: Any = option.get("vec")
        if isinstance(vec, list):
            items = cast("list[Any]", vec)
            return items[0] if items else None
        # Not an Option shape after all — hand it back untouched so validation reports it.
        return option


class WithdrawQueueEntry(BaseModel):
    """Indexed entry from the trading API (normalized amounts, all statuses)."""

    model_config = ConfigDict(populate_by_name=True)

    user: str
    recipient: str | None = None
    market: str | None = None
    fungible_amount: float
    #: Amount processed in this event row; always ``0`` for Queued and Cancelled rows. Partial
    #: fills each emit their own row under the same ``request_id``.
    processed_amount: float
    request_id: str
    status: WithdrawQueueStatus
    #: Only meaningful when ``status == "Cancelled"``; ``None`` there means the reason is unknown
    #: (forward-compat for new cancel reasons).
    cancel_reason: str | None = None
    #: Timestamp of the latest event for this entry (ms since epoch).
    timestamp_ms: int
    #: When the withdrawal was originally queued (ms since epoch). ``None`` on WS deltas whose
    #: Queued event was in a different batch, on replay-reordered rows, and on backfill timeouts.
    #: Do not fall back to ``timestamp_ms`` for display — that is the terminal event's time.
    queued_at_ms: int | None = None
    #: Aptos ledger version; the merge ordering key.
    transaction_version: int

    _check_request_id = field_validator("request_id")(_validate_request_id)


class WithdrawQueueResponse(BaseModel):
    """Paginated response from the indexed HTTP API.

    ``total_count`` counts event rows, not unique withdrawals: without a ``status`` filter a
    Queued-then-Processed withdrawal contributes two rows. Always pass a ``status`` filter when
    using ``total_count`` for pagination display.
    """

    model_config = ConfigDict(populate_by_name=True)

    items: list[WithdrawQueueEntry]
    total_count: int


class WithdrawQueueUpdate(BaseModel):
    """WS payload shape (the topic is stripped before parsing)."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[WithdrawQueueEntry]


def merge_withdraw_queue_entries(
    *,
    existing: list[WithdrawQueueEntry],
    delta: list[WithdrawQueueEntry],
) -> list[WithdrawQueueEntry]:
    """Merge incremental WS deltas into an existing entry list.

    Matches by ``request_id`` and applies a delta only when its ``transaction_version`` is
    strictly greater — the indexer delivers at-least-once, so ``>=`` would let a duplicate
    re-overwrite merged fields with ``None``. ``recipient`` / ``market`` / ``queued_at_ms`` are
    merged field-wise, preserving non-``None`` values already known. ``cancel_reason`` is merged
    the same way but only ever between ``Cancelled`` rows, so a non-terminal row can never
    inherit a stale reason.

    Argument order matters on WS reconnect: pass ``existing=ws_cache, delta=http_snapshot`` so
    HTTP data cannot regress entries the WS has already advanced.

    Returns a new list sorted by queue time descending; terminal entries with no ``queued_at_ms``
    sink to the bottom. Neither input is mutated.
    """
    # Two-pass dedup of `existing`: the highest-version row per request_id is the base, then the
    # write-once enrichment fields are backfilled from lower-version rows. Without this, an HTTP
    # response holding both a Queued row (enriched) and a Processed row (nulls) would lose the
    # enrichment when the Processed row wins on version.
    grouped: dict[str, list[WithdrawQueueEntry]] = {}
    for entry in existing:
        grouped.setdefault(entry.request_id, []).append(entry)

    merged: dict[str, WithdrawQueueEntry] = {}
    for request_id, rows in grouped.items():
        best = max(rows, key=lambda row: row.transaction_version)
        recipient = best.recipient
        market = best.market
        queued_at_ms = best.queued_at_ms
        cancel_reason = best.cancel_reason
        for row in rows:
            if recipient is None and row.recipient is not None:
                recipient = row.recipient
            if market is None and row.market is not None:
                market = row.market
            if queued_at_ms is None and row.queued_at_ms is not None:
                queued_at_ms = row.queued_at_ms
            # Same rule as the delta pass below: a reason only ever travels between Cancelled
            # rows, so a Queued row can't end up wearing one.
            if (
                cancel_reason is None
                and best.status == "Cancelled"
                and row.status == "Cancelled"
                and row.cancel_reason is not None
            ):
                cancel_reason = row.cancel_reason
        merged[request_id] = best.model_copy(
            update={
                "recipient": recipient,
                "market": market,
                "queued_at_ms": queued_at_ms,
                "cancel_reason": cancel_reason if best.status == "Cancelled" else None,
            }
        )

    for update in delta:
        prev = merged.get(update.request_id)
        if prev is None:
            merged[update.request_id] = update
            continue
        if update.transaction_version <= prev.transaction_version:
            continue
        # Only carry cancel_reason forward onto a Cancelled entry, and only from a previously
        # Cancelled one — otherwise a Queued row could end up wearing a stale reason.
        if update.status == "Cancelled":
            cancel_reason = update.cancel_reason
            if cancel_reason is None and prev.status == "Cancelled":
                cancel_reason = prev.cancel_reason
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
        # For Queued entries timestamp_ms *is* the queue time; for terminal entries it is the
        # completion time, which would sort them as if newly queued — sink those instead.
        return entry.timestamp_ms if entry.status == "Queued" else 0

    return sorted(merged.values(), key=_queue_time, reverse=True)


def _is_empty_queue_error(exc: ApiError) -> bool:
    try:
        body = json.loads(str(exc))
    except ValueError:
        return False
    if not isinstance(body, dict):
        return False
    return cast("dict[str, Any]", body).get("error_code") in _EMPTY_QUEUE_ERROR_CODES


class WithdrawQueueReader(BaseReader):
    """Reader for withdrawal-queue data.

    Two data paths: ``get_by_addr`` / ``subscribe_by_addr`` read the indexed HTTP + WS API (the
    primary source), while ``get_pending_withdrawals`` issues a direct on-chain view call as a
    liveness-check fallback (raw chain units, Queued items only).
    """

    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        status: WithdrawQueueStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> WithdrawQueueResponse:
        """Withdrawal-queue entries for an account from the indexed API.

        Use ``request_id`` as the stable key to reconcile entries with WS updates. Without a
        ``status`` filter the response may contain several rows per ``request_id`` (the original
        Queued row plus the terminal Processed/Cancelled one) — deduplicate by ``request_id``,
        keeping the highest ``transaction_version``.

        The server defaults to ``limit=10, offset=0``; the max ``limit`` is 200.
        """
        params: dict[str, str] = {"account": sub_addr}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if status is not None:
            params["status"] = status

        response, _, _ = await self.get_request(
            model=WithdrawQueueResponse,
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
        """Subscribe to real-time withdrawal-queue updates for a subaccount.

        There is no initial snapshot — this topic is streaming-only. Subscribe first, then call
        ``get_by_addr`` and merge with :func:`merge_withdraw_queue_entries` (passing the WS cache
        as ``existing``). Repeat that order on every reconnect.

        All messages are incremental deltas covering only the current indexer batch, never the
        full history, so merge by ``request_id`` rather than replacing the cache.
        """
        topic = f"withdraw_queue:{sub_addr}"
        return self.ws.subscribe(topic, WithdrawQueueUpdate, on_data)

    async def get_pending_withdrawals(
        self, user_addr: str | AccountAddress
    ) -> list[PendingWithdrawRequest]:
        """Pending withdrawal requests from the async withdrawal queue (on-chain view).

        This is a liveness-check fallback, not the primary data source: it returns only
        currently-Queued items, in raw chain units. Use :meth:`get_by_addr` for the full history
        with normalized amounts, correlating on ``request_id``.

        Returns ``[]`` when the queue module isn't initialized or the user has no pending
        requests. ``resource_not_found`` is also swallowed, which means a misconfigured
        ``package`` address returns ``[]`` rather than raising — an accepted tradeoff for a
        fallback path. Other RPC and validation errors propagate; a validation error means the
        on-chain struct shape changed, so watch for it after contract upgrades.
        """
        normalized = (
            user_addr
            if isinstance(user_addr, AccountAddress)
            else AccountAddress.from_str_relaxed(user_addr)
        )
        try:
            result_bytes = await self.aptos.view(
                f"{self.config.deployment.package}::async_withdraw_queue::get_pending_withdrawals",
                [],
                [str(normalized)],
            )
        except ApiError as exc:
            if _is_empty_queue_error(exc):
                return []
            raise
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return [PendingWithdrawRequest.model_validate(item) for item in result[0]]
