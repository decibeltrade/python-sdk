"""Tests for the readers added for TypeScript-SDK parity (spot contexts, points, campaigns,
referrals, single-order lookup, user fees)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel.read._base import BaseReader, ReaderDeps


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


def _patch_get(reader: BaseReader, response: Any) -> Any:
    """Patch a reader's get_request to return ``response`` and expose the recorded call."""
    return patch.object(reader, "get_request", new=AsyncMock(return_value=(response, 200, "OK")))


def _url_of(mock: Any) -> str:
    call = mock.call_args
    return call.args[1] if len(call.args) > 1 else call.kwargs.get("url", "")


# ---------------------------------------------------------------------------
# SpotAssetContextsReader
# ---------------------------------------------------------------------------


class TestSpotAssetContextsReader:
    async def test_get_all(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._spot_asset_contexts import (
            SpotAssetContext,
            SpotAssetContextsReader,
            _SpotAssetContextList,
        )

        context = SpotAssetContext(
            market_addr="0xmarket",
            name="APT/USDC",
            ticker_id="APT_USDC",
            base_asset_addr="0xbase",
            quote_asset_addr="0xquote",
            base_decimals=8,
            quote_decimals=6,
            last_price=5.25,
            mid=5.24,
            prev_day_price=5.0,
            volume_24h_base=100.0,
            volume_24h_quote=525.0,
            high_24h=5.5,
            low_24h=4.9,
            timestamp_unix_ms=1_700_000_000_000,
        )
        reader = SpotAssetContextsReader(reader_deps)

        with _patch_get(reader, _SpotAssetContextList([context])) as mock_req:
            result = await reader.get_all()

        assert result == [context]
        assert "/api/v1/spot/asset_contexts" in _url_of(mock_req)

    def test_untraded_market_fields_are_nullable(self) -> None:
        from decibel.read._spot_asset_contexts import SpotAssetContext

        context = SpotAssetContext.model_validate(
            {
                "market_addr": "0xmarket",
                "name": "APT/USDC",
                "ticker_id": "APT_USDC",
                "base_asset_addr": "0xbase",
                "quote_asset_addr": "0xquote",
                "base_decimals": 8,
                "quote_decimals": 6,
                "last_price": None,
                "mid": None,
                "prev_day_price": None,
                "volume_24h_base": 0.0,
                "volume_24h_quote": 0.0,
                "high_24h": None,
                "low_24h": None,
                "timestamp_unix_ms": 1,
            }
        )
        assert context.last_price is None
        assert context.mid is None


# ---------------------------------------------------------------------------
# Points family: amps, tier, global stats, streaks, leaderboard
# ---------------------------------------------------------------------------


class TestTradingAmpsReader:
    async def test_get_by_owner_minimal(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._trading_amps import OwnerTradingAmps, TradingAmpsReader

        amps = OwnerTradingAmps(owner="0xowner", total_amps=12.5, breakdown=None)
        reader = TradingAmpsReader(reader_deps)

        with _patch_get(reader, amps) as mock_req:
            result = await reader.get_by_owner("0xowner")

        assert result is amps
        assert "/api/v1/points/trading/amps" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {"owner": "0xowner"}

    async def test_season_and_days_filters(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._trading_amps import OwnerTradingAmps, TradingAmpsReader

        reader = TradingAmpsReader(reader_deps)
        amps = OwnerTradingAmps(owner="0xowner", total_amps=0.0)

        with _patch_get(reader, amps) as mock_req:
            await reader.get_by_owner("0xowner", season="season1", days=7)

        assert mock_req.call_args.kwargs["params"] == {
            "owner": "0xowner",
            "season": "season1",
            "days": "7",
        }

    def test_breakdown_parses(self) -> None:
        from decibel.read._trading_amps import OwnerTradingAmps

        amps = OwnerTradingAmps.model_validate(
            {
                "owner": "0xowner",
                "total_amps": 3.0,
                "breakdown": [{"account": "0xsub", "total_amps": 3.0}],
            }
        )
        assert amps.breakdown is not None
        assert amps.breakdown[0].account == "0xsub"


class TestTierReader:
    async def test_get_by_owner(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._tier import TierInfo, TierReader

        info = TierInfo(owner="0xowner", total_amps=100.0, rank=3, current_tier="gold", tiers=[])
        reader = TierReader(reader_deps)

        with _patch_get(reader, info) as mock_req:
            result = await reader.get_by_owner("0xowner")

        assert result is info
        assert "/api/v1/points/tier" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {"owner": "0xowner"}

    def test_unranked_owner(self) -> None:
        from decibel.read._tier import TierInfo

        info = TierInfo.model_validate({"owner": "0xowner", "total_amps": 0.0, "tiers": []})
        assert info.rank is None
        assert info.current_tier is None


class TestGlobalPointsStatsReader:
    async def test_get(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._global_points_stats import GlobalPointsStats, GlobalPointsStatsReader

        stats = GlobalPointsStats(total_users=10, total_amps_distributed=1000.0)
        reader = GlobalPointsStatsReader(reader_deps)

        with _patch_get(reader, stats) as mock_req:
            result = await reader.get()

        assert result is stats
        assert "/api/v1/points/global" in _url_of(mock_req)


class TestStreaksReader:
    async def test_get_by_owner(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._streaks import AccountStreaks, StreaksReader

        streaks = AccountStreaks(
            owner="0xowner",
            current_streak=3,
            streak_ipoints=1.0,
            streak_amps_estimate=2.0,
            grace_days_available=1,
            grace_days_used=0,
            qualifying_dates=["2026-08-15"],
        )
        reader = StreaksReader(reader_deps)

        with _patch_get(reader, streaks) as mock_req:
            result = await reader.get_by_owner("0xowner")

        assert result is streaks
        assert "/api/v1/streaks/account" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {"owner": "0xowner"}

    def test_parses_the_camelcase_wire_shape(self) -> None:
        # This is the one points route that serves camelCase; the field aliases carry it.
        from decibel.read._streaks import AccountStreaks

        streaks = AccountStreaks.model_validate(
            {
                "owner": "0xowner",
                "currentStreak": 5,
                "streakIpoints": 12.5,
                "streakAmpsEstimate": 30.0,
                "graceDaysAvailable": 2,
                "graceDaysUsed": 1,
                "qualifyingDates": ["2026-08-15", "2026-08-16"],
            }
        )
        assert streaks.current_streak == 5
        assert streaks.streak_amps_estimate == 30.0
        assert streaks.qualifying_dates == ["2026-08-15", "2026-08-16"]


class TestPointsLeaderboardReader:
    async def test_no_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._points_leaderboard import (
            PointsLeaderboardReader,
            PointsLeaderboardResponse,
        )

        reader = PointsLeaderboardReader(reader_deps)
        response = PointsLeaderboardResponse(items=[], total_count=0)

        with _patch_get(reader, response) as mock_req:
            await reader.get_points_leaderboard()

        assert "/api/v1/points_leaderboard" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] is None

    async def test_all_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._points_leaderboard import (
            PointsLeaderboardReader,
            PointsLeaderboardResponse,
        )

        reader = PointsLeaderboardReader(reader_deps)

        with _patch_get(reader, PointsLeaderboardResponse(items=[], total_count=0)) as mock_req:
            await reader.get_points_leaderboard(
                limit=50,
                offset=100,
                search_term="0xabc",
                sort_key="realized_pnl",
                sort_dir="ASC",
                tier="diamond",
            )

        assert mock_req.call_args.kwargs["params"] == {
            "limit": "50",
            "offset": "100",
            "search_term": "0xabc",
            "sort_key": "realized_pnl",
            "sort_dir": "ASC",
            "tier": "diamond",
        }

    def test_bonus_amps_defaults_to_zero(self) -> None:
        from decibel.read._points_leaderboard import PointsLeaderboardItem

        item = PointsLeaderboardItem.model_validate(
            {
                "rank": 1,
                "owner": "0xowner",
                "total_amps": 10.0,
                "realized_pnl": 1.0,
                "referral_amps": 0.0,
                "vault_amps": 0.0,
                "streak_amps": 0.0,
            }
        )
        assert item.bonus_amps == 0


# ---------------------------------------------------------------------------
# UserOrdersReader (single-order lookup)
# ---------------------------------------------------------------------------


class TestUserOrdersReader:
    async def test_lookup_by_order_id(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_orders import UserOrdersReader

        reader = UserOrdersReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_order(sub_addr="0xuser", market="0xmarket", order_id="42")

        assert "/api/v1/orders" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {
            "account": "0xuser",
            "market": "0xmarket",
            "order_id": "42",
        }

    async def test_lookup_by_client_order_id(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_orders import UserOrdersReader

        reader = UserOrdersReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_order(sub_addr="0xuser", market="0xmarket", client_order_id="c-1")

        params = mock_req.call_args.kwargs["params"]
        assert params["client_order_id"] == "c-1"
        assert "order_id" not in params

    async def test_asset_type_omitted_by_default(self, reader_deps: ReaderDeps) -> None:
        # Deliberate: with no asset_type the API checks perp then falls through to spot, which is
        # what a lookup by id wants.
        from decibel.read._user_orders import UserOrdersReader

        reader = UserOrdersReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_order(sub_addr="0xuser", market="0xmarket", order_id="42")

        assert "asset_type" not in mock_req.call_args.kwargs["params"]

    async def test_explicit_asset_type_is_sent(self, reader_deps: ReaderDeps) -> None:
        from decibel._asset_type import AssetTypeName
        from decibel.read._user_orders import UserOrdersReader

        reader = UserOrdersReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_order(
                sub_addr="0xuser",
                market="0xmarket",
                order_id="42",
                asset_type=AssetTypeName.SPOT,
            )

        assert mock_req.call_args.kwargs["params"]["asset_type"] == "spot"

    async def test_requires_exactly_one_id(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_orders import UserOrdersReader

        reader = UserOrdersReader(reader_deps)

        with pytest.raises(ValueError, match="exactly one"):
            await reader.get_order(sub_addr="0xuser", market="0xmarket")
        with pytest.raises(ValueError, match="exactly one"):
            await reader.get_order(
                sub_addr="0xuser", market="0xmarket", order_id="1", client_order_id="c-1"
            )


# ---------------------------------------------------------------------------
# UserFeesReader
# ---------------------------------------------------------------------------


_FEE_SCHEDULE: dict[str, Any] = {
    "taker": 0.00034,
    "maker": 0.00011,
    "tiers": {"vip": [], "market_maker": []},
    "referral_discount": 0.0,
}


class TestUserFeesReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_fees import UserFeesReader

        reader = UserFeesReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_by_addr("0xuser")

        assert "/api/v1/user_fee_rates" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {"account": "0xuser"}

    def test_per_product_blocks_are_optional(self) -> None:
        # The perp/spot split is still rolling out server-side; the legacy shape must still parse.
        from decibel.read._user_fees import UserFees

        fees = UserFees.model_validate(
            {
                "account": "0xuser",
                "daily_user_volume": [],
                "fee_schedule": _FEE_SCHEDULE,
                "user_taker_rate": 0.00034,
                "user_maker_rate": 0.00011,
                "fee_tier": 0,
                "active_referral_discount": 0.0,
            }
        )
        assert fees.perp is None
        assert fees.spot is None
        assert fees.volume_weights is None

    def test_parses_the_cross_product_shape(self) -> None:
        from decibel.read._user_fees import UserFees

        product: dict[str, Any] = {
            "fee_tier": 2,
            "fee_schedule": _FEE_SCHEDULE,
            "user_taker_rate": 0.0003,
            "user_maker_rate": 0.00009,
            "daily_user_volume": [
                {
                    "date": "2026-08-16",
                    "volume": "1000",
                    "maker_volume": "400",
                    "taker_volume": "600",
                }
            ],
            "total_window_volume_usd": "1000",
            "active_referral_discount": 0.0,
        }
        fees = UserFees.model_validate(
            {
                "account": "0xuser",
                "daily_user_volume": [],
                "fee_schedule": _FEE_SCHEDULE,
                "user_taker_rate": 0.0003,
                "user_maker_rate": 0.00009,
                "fee_tier": 2,
                "active_referral_discount": 0.0,
                "perp": product,
                "spot": {**product, "fee_tier": 1},
                "weighted_volume_usd": "1500",
                "volume_weights": {"perp": 1.0, "spot": 0.5},
            }
        )
        assert fees.perp is not None
        assert fees.spot is not None
        # Perp and spot tiers can differ for one user: perp uses perp-only window volume.
        assert (fees.perp.fee_tier, fees.spot.fee_tier) == (2, 1)
        assert fees.volume_weights is not None
        assert fees.volume_weights.spot == 0.5


# ---------------------------------------------------------------------------
# CampaignsReader
# ---------------------------------------------------------------------------


class TestCampaignsReader:
    async def test_get_active(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._campaigns import CampaignsReader, _ActiveCampaigns

        reader = CampaignsReader(reader_deps)

        with _patch_get(reader, _ActiveCampaigns([])) as mock_req:
            result = await reader.get_active()

        assert result == []
        assert "/api/v1/campaigns/active" in _url_of(mock_req)

    async def test_get_summary(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._campaigns import CampaignsReader

        reader = CampaignsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_summary(account_address="0xuser", limit=5, offset=10)

        assert "/api/v1/campaigns/account" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {
            "account": "0xuser",
            "limit": "5",
            "offset": "10",
        }

    def test_campaign_metadata_parses(self) -> None:
        from decibel.read._campaigns import CampaignMetadata

        campaign = CampaignMetadata.model_validate(
            {
                "campaign_id": 1,
                "campaign_type": "fee_rebate",
                "status": "active",
                "title": "Fee rebates",
                "reward_asset": "0xusdc",
                "start_ts_sec": 1,
                "end_ts_sec": 2,
                "claim_start_ts_sec": 3,
                "claim_end_ts_sec": 4,
                "total_funded": 100.0,
            }
        )
        assert campaign.description is None
        assert campaign.campaign_type == "fee_rebate"


# ---------------------------------------------------------------------------
# ReferralsReader
# ---------------------------------------------------------------------------


class TestReferralsReader:
    async def test_validate_code_url_encodes(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.validate_code("a/b c")

        assert _url_of(mock_req).endswith("/api/v1/referrals/code/a%2Fb%20c")

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get_account_referral", "/api/v1/referrals/account/"),
            ("get_referrer_stats", "/api/v1/referrals/stats/"),
            ("get_affiliate_codes", "/api/v1/affiliates/codes/"),
            ("get_affiliate_earnings", "/api/v1/affiliates/earnings/"),
        ],
    )
    async def test_account_path_segments_are_url_encoded(
        self, reader_deps: ReaderDeps, method: str, path: str
    ) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await getattr(reader, method)("a/b c")

        assert _url_of(mock_req).endswith(f"{path}a%2Fb%20c")

    async def test_analytics_account_segment_is_url_encoded(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_affiliate_code_analytics("a/b c")

        assert _url_of(mock_req).endswith("/api/v1/affiliates/codes/a%2Fb%20c/analytics")

    async def test_get_account_referral(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_account_referral("0xuser")

        assert _url_of(mock_req).endswith("/api/v1/referrals/account/0xuser")

    async def test_redeem_code_posts(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with patch.object(
            reader, "post_request", new=AsyncMock(return_value=(MagicMock(), 200, "OK"))
        ) as mock_req:
            await reader.redeem_code(referral_code="CODE", account="0xuser")

        assert "/api/v1/referrals/redeem" in mock_req.call_args.kwargs["url"]
        assert mock_req.call_args.kwargs["body"] == {
            "referral_code": "CODE",
            "account": "0xuser",
        }

    async def test_get_user_referrals_pagination(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader, _UserReferrals

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, _UserReferrals([])) as mock_req:
            result = await reader.get_user_referrals(
                referrer_account="0xreferrer", limit=10, offset=20
            )

        assert result == []
        assert "/api/v1/referrals/users" in _url_of(mock_req)
        assert mock_req.call_args.kwargs["params"] == {
            "referrer_account": "0xreferrer",
            "limit": "10",
            "offset": "20",
        }

    async def test_affiliate_code_analytics_is_a_separate_route(
        self, reader_deps: ReaderDeps
    ) -> None:
        # Split from get_affiliate_codes so the nav-bar metadata call skips the analytics JOIN.
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_affiliate_codes("0xuser")
        assert _url_of(mock_req).endswith("/api/v1/affiliates/codes/0xuser")

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_affiliate_code_analytics("0xuser")
        assert _url_of(mock_req).endswith("/api/v1/affiliates/codes/0xuser/analytics")

    async def test_get_affiliate_earnings(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._referrals import ReferralsReader

        reader = ReferralsReader(reader_deps)

        with _patch_get(reader, MagicMock()) as mock_req:
            await reader.get_affiliate_earnings("0xuser")

        assert _url_of(mock_req).endswith("/api/v1/affiliates/earnings/0xuser")
        assert mock_req.call_args.kwargs["params"] == {"limit": "1000"}


# ---------------------------------------------------------------------------
# RWA insights (types only — the data comes from the BFF, not trading_http_url)
# ---------------------------------------------------------------------------


class TestRwaInsights:
    def test_is_rwa_ticker(self) -> None:
        from decibel.read._rwa_insights import RWA_TICKERS, is_rwa_ticker

        assert is_rwa_ticker("NVDA") is True
        assert is_rwa_ticker("BTC") is False
        # Case-sensitive by design: tickers are uppercase everywhere on the wire.
        assert is_rwa_ticker("nvda") is False
        assert all(is_rwa_ticker(t) for t in RWA_TICKERS)

    def test_key_statistics_are_all_nullable(self) -> None:
        from decibel.read._rwa_insights import RwaKeyStatistics

        stats = RwaKeyStatistics.model_validate(
            {
                "market_cap": None,
                "volume": None,
                "average_volume": None,
                "pe_ratio": None,
                "week52_high": None,
                "week52_low": None,
            }
        )
        assert stats.market_cap is None
