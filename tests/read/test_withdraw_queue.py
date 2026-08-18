"""Tests for the withdraw-queue reader and its merge/classification helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from aptos_sdk.async_client import ApiError

from decibel.read._base import ReaderDeps
from decibel.read._withdraw_queue import (
    PendingWithdrawRequest,
    WithdrawQueueEntry,
    WithdrawQueueReader,
    WithdrawQueueResponse,
    WithdrawQueueUpdate,
    _is_empty_queue_error,
    is_known_cancel_reason,
    merge_withdraw_queue_entries,
)


@pytest.fixture
def reader_deps(test_config: object) -> ReaderDeps:
    return ReaderDeps(
        config=test_config,  # type: ignore[arg-type]
        ws=MagicMock(),
        aptos=MagicMock(),
        api_key="test-key",
        http_client=AsyncMock(spec=httpx.AsyncClient),
        http_client_sync=MagicMock(spec=httpx.Client),
    )


_USER_ADDR = "0x1a2b3c"


def _entry(
    request_id: str,
    *,
    status: str = "Queued",
    transaction_version: int = 1,
    timestamp_ms: int = 1_000,
    queued_at_ms: int | None = None,
    recipient: str | None = None,
    market: str | None = None,
    cancel_reason: str | None = None,
    fungible_amount: float = 10.0,
    processed_amount: float = 0.0,
) -> WithdrawQueueEntry:
    return WithdrawQueueEntry(
        user="0xuser",
        recipient=recipient,
        market=market,
        fungible_amount=fungible_amount,
        processed_amount=processed_amount,
        request_id=request_id,
        status=status,  # type: ignore[arg-type]
        cancel_reason=cancel_reason,
        timestamp_ms=timestamp_ms,
        queued_at_ms=queued_at_ms,
        transaction_version=transaction_version,
    )


class TestRequestIdValidation:
    def test_accepts_numeric_string(self) -> None:
        assert _entry("18446744073709551615").request_id == "18446744073709551615"

    @pytest.mark.parametrize("bad", ["", "0x1", "12a", "-1", "1" * 21])
    def test_rejects_non_u64_strings(self, bad: str) -> None:
        with pytest.raises(ValueError, match="numeric string"):
            _entry(bad)


class TestIsKnownCancelReason:
    @pytest.mark.parametrize(
        "reason",
        ["CancelledByUser", "InsufficientWithdrawableBalance", "DepositCheckFailed"],
    )
    def test_known(self, reason: str) -> None:
        assert is_known_cancel_reason(reason) is True

    def test_unknown_reason_passes_through(self) -> None:
        assert is_known_cancel_reason("SomeFutureReason") is False


class TestMergeWithdrawQueueEntries:
    def test_new_request_ids_are_appended(self) -> None:
        merged = merge_withdraw_queue_entries(existing=[_entry("1")], delta=[_entry("2")])
        assert {e.request_id for e in merged} == {"1", "2"}

    def test_higher_version_wins(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[_entry("1", status="Queued", transaction_version=1)],
            delta=[_entry("1", status="Processed", transaction_version=2, processed_amount=10.0)],
        )
        assert len(merged) == 1
        assert merged[0].status == "Processed"

    def test_duplicate_delivery_is_ignored(self) -> None:
        # At-least-once delivery: an equal-version redelivery must not clobber merged fields.
        merged = merge_withdraw_queue_entries(
            existing=[_entry("1", transaction_version=5, recipient="0xdest", queued_at_ms=900)],
            delta=[_entry("1", transaction_version=5, recipient=None, queued_at_ms=None)],
        )
        assert merged[0].recipient == "0xdest"
        assert merged[0].queued_at_ms == 900

    def test_lower_version_is_ignored(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[_entry("1", status="Processed", transaction_version=9)],
            delta=[_entry("1", status="Queued", transaction_version=2)],
        )
        assert merged[0].status == "Processed"
        assert merged[0].transaction_version == 9

    def test_enrichment_fields_are_carried_forward(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry("1", transaction_version=1, recipient="0xdest", market="0xm", queued_at_ms=5)
            ],
            delta=[_entry("1", status="Processed", transaction_version=2)],
        )
        assert (merged[0].recipient, merged[0].market, merged[0].queued_at_ms) == (
            "0xdest",
            "0xm",
            5,
        )

    def test_existing_rows_for_one_id_are_deduped_before_merging(self) -> None:
        # A single HTTP page can hold both the enriched Queued row and the bare Processed row.
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry("1", transaction_version=1, recipient="0xdest", queued_at_ms=100),
                _entry("1", status="Processed", transaction_version=2),
            ],
            delta=[],
        )
        assert len(merged) == 1
        assert merged[0].status == "Processed"
        assert merged[0].recipient == "0xdest"
        assert merged[0].queued_at_ms == 100

    def test_cancel_reason_carried_only_between_cancelled_rows(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry("1", status="Cancelled", transaction_version=1, cancel_reason="ByUser")
            ],
            delta=[_entry("1", status="Cancelled", transaction_version=2)],
        )
        assert merged[0].cancel_reason == "ByUser"

    def test_cancel_reason_dropped_on_non_cancelled_status(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry("1", status="Cancelled", transaction_version=1, cancel_reason="ByUser")
            ],
            delta=[_entry("1", status="Queued", transaction_version=2)],
        )
        assert merged[0].cancel_reason is None

    def test_sorted_by_queue_time_descending(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry("1", queued_at_ms=100),
                _entry("2", queued_at_ms=300),
                _entry("3", queued_at_ms=200),
            ],
            delta=[],
        )
        assert [e.request_id for e in merged] == ["2", "3", "1"]

    def test_terminal_rows_without_queue_time_sink(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry("1", status="Processed", timestamp_ms=9_999, queued_at_ms=None),
                _entry("2", status="Queued", timestamp_ms=10, queued_at_ms=None),
            ],
            delta=[],
        )
        assert [e.request_id for e in merged] == ["2", "1"]

    def test_inputs_are_not_mutated(self) -> None:
        existing = [_entry("1", transaction_version=1, recipient="0xdest")]
        delta = [_entry("1", status="Processed", transaction_version=2)]
        merge_withdraw_queue_entries(existing=existing, delta=delta)
        assert existing[0].status == "Queued"
        assert delta[0].recipient is None

    def test_empty_inputs(self) -> None:
        assert merge_withdraw_queue_entries(existing=[], delta=[]) == []


class TestPendingWithdrawRequestOption:
    def test_unwraps_some(self) -> None:
        request = PendingWithdrawRequest(
            request_id="1",
            user="0xuser",
            recipient="0xdest",
            market={"vec": ["0xmarket"]},  # type: ignore[arg-type]
            metadata="0xmeta",
            fungible_amount="1000000",
            created_at="1700000000",
        )
        assert request.market == "0xmarket"

    def test_unwraps_none(self) -> None:
        request = PendingWithdrawRequest(
            request_id="1",
            user="0xuser",
            recipient="0xdest",
            market={"vec": []},  # type: ignore[arg-type]
            metadata="0xmeta",
            fungible_amount="1000000",
            created_at="1700000000",
        )
        assert request.market is None

    def test_plain_string_passes_through(self) -> None:
        request = PendingWithdrawRequest(
            request_id="1",
            user="0xuser",
            recipient="0xdest",
            market="0xmarket",
            metadata="0xmeta",
            fungible_amount="1000000",
            created_at="1700000000",
        )
        assert request.market == "0xmarket"


class TestIsEmptyQueueError:
    @pytest.mark.parametrize(
        "code", ["module_not_found", "function_not_found", "resource_not_found"]
    )
    def test_recognised_codes(self, code: str) -> None:
        assert _is_empty_queue_error(ApiError(f'{{"error_code":"{code}"}}', 404)) is True

    def test_other_error_code(self) -> None:
        assert _is_empty_queue_error(ApiError('{"error_code":"vm_error"}', 400)) is False

    def test_non_json_message(self) -> None:
        assert _is_empty_queue_error(ApiError("upstream timed out", 504)) is False

    def test_json_that_is_not_an_object(self) -> None:
        assert _is_empty_queue_error(ApiError("[1, 2, 3]", 500)) is False


class TestWithdrawQueueReader:
    async def test_get_by_addr_minimal(self, reader_deps: ReaderDeps) -> None:
        reader = WithdrawQueueReader(reader_deps)
        response = WithdrawQueueResponse(items=[], total_count=0)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result is response
        kwargs = mock_req.call_args.kwargs
        assert "/api/v1/withdraw_queue" in kwargs["url"]
        assert kwargs["params"] == {"account": "0xuser"}

    async def test_get_by_addr_with_filters(self, reader_deps: ReaderDeps) -> None:
        reader = WithdrawQueueReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (WithdrawQueueResponse(items=[], total_count=0), 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser", status="Queued", limit=10, offset=20)

        params = mock_req.call_args.kwargs["params"]
        assert params == {"account": "0xuser", "status": "Queued", "limit": "10", "offset": "20"}

    def test_subscribe_by_addr_topic(self, reader_deps: ReaderDeps) -> None:
        reader = WithdrawQueueReader(reader_deps)
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", MagicMock())

        args = reader_deps.ws.subscribe.call_args[0]
        assert args[0] == "withdraw_queue:0xuser"
        assert args[1] is WithdrawQueueUpdate

    async def test_get_pending_withdrawals_swallows_empty_queue_errors(
        self, reader_deps: ReaderDeps
    ) -> None:
        reader = WithdrawQueueReader(reader_deps)
        reader_deps.aptos.view = AsyncMock(
            side_effect=ApiError('{"error_code":"resource_not_found"}', 404)
        )

        assert await reader.get_pending_withdrawals(_USER_ADDR) == []

    async def test_get_pending_withdrawals_reraises_real_errors(
        self, reader_deps: ReaderDeps
    ) -> None:
        reader = WithdrawQueueReader(reader_deps)
        reader_deps.aptos.view = AsyncMock(side_effect=ApiError('{"error_code":"vm_error"}', 400))

        with pytest.raises(ApiError):
            await reader.get_pending_withdrawals(_USER_ADDR)

    async def test_get_pending_withdrawals_parses_view_result(
        self, reader_deps: ReaderDeps
    ) -> None:
        payload: list[list[dict[str, Any]]] = [
            [
                {
                    "request_id": "7",
                    "user": "0xuser",
                    "recipient": "0xdest",
                    "market": {"vec": []},
                    "metadata": "0xmeta",
                    "fungible_amount": "1000000",
                    "created_at": "1700000000",
                }
            ]
        ]
        reader = WithdrawQueueReader(reader_deps)
        import json as _json

        reader_deps.aptos.view = AsyncMock(return_value=_json.dumps(payload).encode())

        result = await reader.get_pending_withdrawals(_USER_ADDR)

        assert len(result) == 1
        assert result[0].request_id == "7"
        assert result[0].market is None


class TestMergeExistingCancelReason:
    """The `existing` dedup pass backfills `cancel_reason` like the delta pass already did."""

    def test_backfills_reason_from_a_lower_version_cancelled_row(self) -> None:
        # Same withdrawal delivered as two Cancelled rows; only the earlier one carries the reason.
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry(
                    "1",
                    status="Cancelled",
                    transaction_version=1,
                    cancel_reason="DepositCheckFailed",
                ),
                _entry("1", status="Cancelled", transaction_version=2),
            ],
            delta=[],
        )
        assert len(merged) == 1
        assert merged[0].cancel_reason == "DepositCheckFailed"

    def test_keeps_the_winning_rows_own_reason(self) -> None:
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry(
                    "1",
                    status="Cancelled",
                    transaction_version=1,
                    cancel_reason="DepositCheckFailed",
                ),
                _entry(
                    "1", status="Cancelled", transaction_version=2, cancel_reason="CancelledByUser"
                ),
            ],
            delta=[],
        )
        assert merged[0].cancel_reason == "CancelledByUser"

    def test_non_cancelled_winner_never_inherits_a_reason(self) -> None:
        # A Cancelled row replayed alongside a later Processed row must not tag it with a reason.
        merged = merge_withdraw_queue_entries(
            existing=[
                _entry(
                    "1", status="Cancelled", transaction_version=1, cancel_reason="CancelledByUser"
                ),
                _entry("1", status="Processed", transaction_version=2),
            ],
            delta=[],
        )
        assert merged[0].status == "Processed"
        assert merged[0].cancel_reason is None
