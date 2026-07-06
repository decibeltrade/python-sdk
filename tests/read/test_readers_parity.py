"""Tests for the TS-SDK parity readers added to decibel.read.*"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel.read._base import ReaderDeps

if TYPE_CHECKING:
    from decibel._constants import DecibelConfig


@pytest.fixture
def reader_deps(test_config: DecibelConfig) -> ReaderDeps:
    return ReaderDeps(
        config=test_config,
        ws=MagicMock(),
        aptos=MagicMock(),
        api_key="test-key",
        http_client=AsyncMock(spec=httpx.AsyncClient),
        http_client_sync=MagicMock(spec=httpx.Client),
    )


def _base_url(reader_deps: ReaderDeps) -> str:
    return reader_deps.config.trading_http_url


# ---------------------------------------------------------------------------
# CampaignsReader
# ---------------------------------------------------------------------------


class TestCampaignsReader:
    async def test_get_active(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._campaigns import CampaignsReader

        reader = CampaignsReader(reader_deps)
        root = MagicMock()
        root.root = ["campaign"]
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (root, 200, "OK")
            result = await reader.get_active()
        assert result == ["campaign"]
        assert (
            mock_req.call_args.kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/campaigns/active"
        )

    async def test_get_summary(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._campaigns import CampaignsReader

        reader = CampaignsReader(reader_deps)
        summary = MagicMock()
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (summary, 200, "OK")
            result = await reader.get_summary(account_address="0xabc", limit=5, offset=10)
        assert result is summary
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/campaigns/account"
        assert kwargs["params"] == {"account": "0xabc", "limit": "5", "offset": "10"}


# ---------------------------------------------------------------------------
# PointsLeaderboardReader
# ---------------------------------------------------------------------------


class TestPointsLeaderboardReader:
    async def test_get_points_leaderboard(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._points_leaderboard import PointsLeaderboardReader

        reader = PointsLeaderboardReader(reader_deps)
        page = MagicMock()
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (page, 200, "OK")
            result = await reader.get_points_leaderboard(
                limit=20, tier="diamond", sort_key="total_amps"
            )
        assert result is page
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/points_leaderboard"
        assert kwargs["params"] == {"limit": "20", "sort_key": "total_amps", "tier": "diamond"}


# ---------------------------------------------------------------------------
# StreaksReader
# ---------------------------------------------------------------------------


class TestStreaksReader:
    async def test_get_by_owner(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._streaks import AccountStreaks, StreaksReader

        reader = StreaksReader(reader_deps)
        streaks = AccountStreaks.model_validate(
            {
                "owner": "0xabc",
                "currentStreak": 3,
                "streakIpoints": 10,
                "streakAmpsEstimate": 5,
                "graceDaysAvailable": 2,
                "graceDaysUsed": 1,
                "qualifyingDates": ["2026-01-01"],
            }
        )
        assert streaks.current_streak == 3
        assert streaks.qualifying_dates == ["2026-01-01"]
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (streaks, 200, "OK")
            result = await reader.get_by_owner(owner_addr="0xabc")
        assert result is streaks
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/streaks/account"
        assert kwargs["params"] == {"owner": "0xabc"}


# ---------------------------------------------------------------------------
# TradingAmpsReader
# ---------------------------------------------------------------------------


class TestTradingAmpsReader:
    async def test_get_by_owner_with_filters(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._trading_amps import OwnerTradingAmps, TradingAmpsReader

        reader = TradingAmpsReader(reader_deps)
        amps = OwnerTradingAmps(owner="0xabc", total_amps=100.0, breakdown=None)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (amps, 200, "OK")
            result = await reader.get_by_owner(owner_addr="0xabc", season="season1", days=7)
        assert result is amps
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/points/trading/amps"
        assert kwargs["params"] == {"owner": "0xabc", "season": "season1", "days": "7"}


# ---------------------------------------------------------------------------
# TierReader
# ---------------------------------------------------------------------------


class TestTierReader:
    async def test_get_by_owner(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._tier import TierInfo, TierReader

        reader = TierReader(reader_deps)
        tier = TierInfo(owner="0xabc", total_amps=1.0, rank=None, current_tier=None, tiers=[])
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (tier, 200, "OK")
            result = await reader.get_by_owner(owner_addr="0xabc")
        assert result is tier
        assert mock_req.call_args.kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/points/tier"


# ---------------------------------------------------------------------------
# GlobalPointsStatsReader
# ---------------------------------------------------------------------------


class TestGlobalPointsStatsReader:
    async def test_get(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._global_points_stats import GlobalPointsStats, GlobalPointsStatsReader

        reader = GlobalPointsStatsReader(reader_deps)
        stats = GlobalPointsStats(total_users=10, total_amps_distributed=1000)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (stats, 200, "OK")
            result = await reader.get()
        assert result is stats
        assert mock_req.call_args.kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/points/global"


# ---------------------------------------------------------------------------
# ReferralsReader
# ---------------------------------------------------------------------------


class TestReferralsReader:
    async def test_validate_code_url_encodes(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.validate_code("A B")
        assert mock_req.call_args.kwargs["url"].endswith("/api/v1/referrals/code/A%20B")

    async def test_redeem_code_posts_body(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        with patch.object(reader, "post_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.redeem_code(referral_code="CODE", account="0xabc")
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/referrals/redeem"
        assert kwargs["body"] == {"referral_code": "CODE", "account": "0xabc"}

    async def test_get_user_referrals_returns_root(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        root = MagicMock()
        root.root = ["u1", "u2"]
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (root, 200, "OK")
            result = await reader.get_user_referrals(referrer_account="0xabc", limit=2)
        assert result == ["u1", "u2"]
        kwargs = mock_req.call_args.kwargs
        assert kwargs["params"] == {"referrer_account": "0xabc", "limit": "2"}


# ---------------------------------------------------------------------------
# UserFeesReader
# ---------------------------------------------------------------------------


class TestUserFeesReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_fees import UserFeesReader

        reader = UserFeesReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_by_addr(sub_addr="0xabc")
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/user_fee_rates"
        assert kwargs["params"] == {"account": "0xabc"}


# ---------------------------------------------------------------------------
# WithdrawQueueReader
# ---------------------------------------------------------------------------


def _entry(**overrides: object) -> object:
    from decibel.read._withdraw_queue import WithdrawQueueEntry

    base = {
        "user": "0xuser",
        "recipient": "0xrecipient",
        "market": "0xmarket",
        "fungible_amount": 10.0,
        "processed_amount": 0.0,
        "request_id": "1",
        "status": "Queued",
        "cancel_reason": None,
        "timestamp_ms": 1000,
        "queued_at_ms": 1000,
        "transaction_version": 1,
    }
    base.update(overrides)
    return WithdrawQueueEntry.model_validate(base)


class TestWithdrawQueueReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        reader = WithdrawQueueReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_by_addr(sub_addr="0xabc", status="Queued", limit=50, offset=0)
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"] == f"{_base_url(reader_deps)}/api/v1/withdraw_queue"
        assert kwargs["params"] == {
            "account": "0xabc",
            "limit": "50",
            "offset": "0",
            "status": "Queued",
        }

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader, WithdrawQueueUpdate

        reader = WithdrawQueueReader(reader_deps)
        on_data = MagicMock()
        reader.subscribe_by_addr("0xabc", on_data)
        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "withdraw_queue:0xabc"
        assert call_args[0][1] is WithdrawQueueUpdate

    async def test_get_pending_withdrawals(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        reader = WithdrawQueueReader(reader_deps)
        item = {
            "request_id": "7",
            "user": "0xuser",
            "recipient": "0xrecipient",
            "market": {"vec": ["0xmarket"]},
            "metadata": "0x",
            "fungible_amount": "1000000",
            "created_at": "1700000000",
        }
        reader_deps.aptos.view = AsyncMock(return_value=json.dumps([[item]]).encode("utf-8"))
        result = await reader.get_pending_withdrawals("0x" + "aa" * 32)
        assert len(result) == 1
        assert result[0].request_id == "7"
        assert result[0].market == "0xmarket"

    async def test_get_pending_withdrawals_empty_option(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        reader = WithdrawQueueReader(reader_deps)
        item = {
            "request_id": "8",
            "user": "0xuser",
            "recipient": "0xrecipient",
            "market": {"vec": []},
            "metadata": "0x",
            "fungible_amount": "5",
            "created_at": "1700000000",
        }
        reader_deps.aptos.view = AsyncMock(return_value=json.dumps([[item]]).encode("utf-8"))
        result = await reader.get_pending_withdrawals("0x" + "aa" * 32)
        assert result[0].market is None

    async def test_get_pending_withdrawals_swallows_not_found(
        self, reader_deps: ReaderDeps
    ) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        reader = WithdrawQueueReader(reader_deps)
        reader_deps.aptos.view = AsyncMock(side_effect=Exception("module_not_found: nope"))
        assert await reader.get_pending_withdrawals("0x" + "aa" * 32) == []

    async def test_get_pending_withdrawals_reraises_unexpected(
        self, reader_deps: ReaderDeps
    ) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        reader = WithdrawQueueReader(reader_deps)
        reader_deps.aptos.view = AsyncMock(side_effect=Exception("boom"))
        with pytest.raises(Exception, match="boom"):
            await reader.get_pending_withdrawals("0x" + "aa" * 32)


# ---------------------------------------------------------------------------
# withdraw_queue helpers (pure logic)
# ---------------------------------------------------------------------------


class TestWithdrawQueueHelpers:
    def test_is_known_cancel_reason(self) -> None:
        from decibel.read._withdraw_queue import is_known_cancel_reason

        assert is_known_cancel_reason("CancelledByUser") is True
        assert is_known_cancel_reason("SomethingElse") is False

    def test_merge_applies_higher_version(self) -> None:
        from decibel.read._withdraw_queue import merge_withdraw_queue_entries

        existing = [_entry(request_id="1", status="Queued", transaction_version=1)]
        delta = [
            _entry(
                request_id="1",
                status="Processed",
                processed_amount=10.0,
                transaction_version=2,
                queued_at_ms=None,
            )
        ]
        merged = merge_withdraw_queue_entries(existing=existing, delta=delta)  # type: ignore[arg-type]
        assert len(merged) == 1
        assert merged[0].status == "Processed"
        # queued_at_ms preserved from the existing enriched entry
        assert merged[0].queued_at_ms == 1000

    def test_merge_ignores_stale_version(self) -> None:
        from decibel.read._withdraw_queue import merge_withdraw_queue_entries

        existing = [_entry(request_id="1", status="Processed", transaction_version=5)]
        delta = [_entry(request_id="1", status="Queued", transaction_version=2)]
        merged = merge_withdraw_queue_entries(existing=existing, delta=delta)  # type: ignore[arg-type]
        assert merged[0].status == "Processed"

    def test_merge_clears_cancel_reason_for_non_cancelled(self) -> None:
        from decibel.read._withdraw_queue import merge_withdraw_queue_entries

        existing = [
            _entry(
                request_id="1",
                status="Cancelled",
                cancel_reason="CancelledByUser",
                transaction_version=1,
            )
        ]
        delta = [_entry(request_id="1", status="Processed", transaction_version=2)]
        merged = merge_withdraw_queue_entries(existing=existing, delta=delta)  # type: ignore[arg-type]
        assert merged[0].cancel_reason is None

    def test_merge_sorts_queued_before_terminal(self) -> None:
        from decibel.read._withdraw_queue import merge_withdraw_queue_entries

        terminal = _entry(
            request_id="1",
            status="Processed",
            queued_at_ms=None,
            timestamp_ms=9999,
            transaction_version=2,
        )
        queued = _entry(request_id="2", status="Queued", queued_at_ms=5000, transaction_version=1)
        merged = merge_withdraw_queue_entries(existing=[terminal, queued], delta=[])  # type: ignore[arg-type]
        assert [e.request_id for e in merged] == ["2", "1"]


class TestReferralsExtraMethods:
    async def test_get_account_referral(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_account_referral("0xabc")
        assert mock_req.call_args.kwargs["url"].endswith("/api/v1/referrals/account/0xabc")

    async def test_get_referrer_stats(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_referrer_stats("0xabc")
        assert mock_req.call_args.kwargs["url"].endswith("/api/v1/referrals/stats/0xabc")

    async def test_get_affiliate_codes(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_affiliate_codes("0xabc")
        assert mock_req.call_args.kwargs["url"].endswith("/api/v1/affiliates/codes/0xabc")

    async def test_get_affiliate_earnings(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_affiliate_earnings("0xabc")
        kwargs = mock_req.call_args.kwargs
        assert kwargs["url"].endswith("/api/v1/affiliates/earnings/0xabc")
        assert kwargs["params"] == {"limit": "1000"}

    async def test_get_user_referrals_no_page_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)
        root = MagicMock()
        root.root = []
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (root, 200, "OK")
            await reader.get_user_referrals(referrer_account="0xabc")
        assert mock_req.call_args.kwargs["params"] == {"referrer_account": "0xabc"}


class TestPointsLeaderboardAllParams:
    async def test_all_query_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._points_leaderboard import PointsLeaderboardReader

        reader = PointsLeaderboardReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_points_leaderboard(
                limit=5,
                offset=10,
                search_term="alice",
                sort_key="realized_pnl",
                sort_dir="ASC",
                tier="gold",
            )
        assert mock_req.call_args.kwargs["params"] == {
            "limit": "5",
            "offset": "10",
            "search_term": "alice",
            "sort_key": "realized_pnl",
            "sort_dir": "ASC",
            "tier": "gold",
        }

    async def test_no_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._points_leaderboard import PointsLeaderboardReader

        reader = PointsLeaderboardReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_points_leaderboard()
        assert mock_req.call_args.kwargs["params"] is None


class TestWithdrawQueueExtra:
    async def test_get_by_addr_minimal(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._withdraw_queue import WithdrawQueueReader

        reader = WithdrawQueueReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (MagicMock(), 200, "OK")
            await reader.get_by_addr(sub_addr="0xabc")
        assert mock_req.call_args.kwargs["params"] == {"account": "0xabc"}

    def test_pending_withdraw_market_passthrough_string(self) -> None:
        from decibel.read._withdraw_queue import PendingWithdrawRequest

        req = PendingWithdrawRequest.model_validate(
            {
                "request_id": "1",
                "user": "0xuser",
                "recipient": "0xr",
                "market": "0xmarket",
                "metadata": "0x",
                "fungible_amount": "5",
                "created_at": "1700000000",
            }
        )
        assert req.market == "0xmarket"

    def test_merge_new_entry_from_delta(self) -> None:
        from decibel.read._withdraw_queue import merge_withdraw_queue_entries

        delta = [_entry(request_id="9", status="Queued", transaction_version=1)]
        merged = merge_withdraw_queue_entries(existing=[], delta=delta)  # type: ignore[arg-type]
        assert [e.request_id for e in merged] == ["9"]

    def test_merge_dedup_existing_fills_enrichment(self) -> None:
        from decibel.read._withdraw_queue import merge_withdraw_queue_entries

        enriched = _entry(
            request_id="1",
            status="Queued",
            recipient="0xr",
            market="0xm",
            queued_at_ms=100,
            transaction_version=1,
        )
        terminal = _entry(
            request_id="1",
            status="Processed",
            recipient=None,
            market=None,
            queued_at_ms=None,
            transaction_version=2,
        )
        merged = merge_withdraw_queue_entries(existing=[enriched, terminal], delta=[])  # type: ignore[arg-type]
        assert len(merged) == 1
        assert merged[0].status == "Processed"
        assert merged[0].recipient == "0xr"
        assert merged[0].market == "0xm"
        assert merged[0].queued_at_ms == 100
