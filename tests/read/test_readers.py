"""Tests for all reader modules in decibel.read.*"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel.read._base import ReaderDeps

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------


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


def _mock_get(return_value: Any) -> MagicMock:
    """Helper to create a mock for get_request that returns the given value."""
    mock = AsyncMock(return_value=(return_value, 200, "OK"))
    return mock


def _mock_get_root(items: list[Any], model_cls: type) -> Any:
    """Return a RootModel wrapping items."""
    return model_cls(items)


# ---------------------------------------------------------------------------
# AccountOverviewReader
# ---------------------------------------------------------------------------


class TestAccountOverviewReader:
    async def test_get_by_addr_basic(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._account_overview import AccountOverview, AccountOverviewReader

        overview = AccountOverview(
            perp_equity_balance=100.0,
            unrealized_pnl=5.0,
            unrealized_funding_cost=0.5,
            cross_margin_ratio=0.1,
            maintenance_margin=0.05,
            cross_account_leverage_ratio=None,
            volume=None,
            net_deposits=None,
            all_time_return=None,
            pnl_90d=None,
            sharpe_ratio=None,
            max_drawdown=None,
            weekly_win_rate_12w=None,
            average_cash_position=None,
            average_leverage=None,
            cross_account_position=10.0,
            total_margin=500.0,
            usdc_cross_withdrawable_balance=100.0,
            usdc_isolated_withdrawable_balance=0.0,
            realized_pnl=None,
            liquidation_fees_paid=None,
            liquidation_losses=None,
        )
        reader = AccountOverviewReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (overview, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result is overview
        mock_req.assert_called_once()
        call_kwargs = mock_req.call_args.kwargs
        assert "account" in call_kwargs["params"]
        assert call_kwargs["params"]["account"] == "0xuser"

    async def test_get_by_addr_with_volume_window(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._account_overview import (
            AccountOverview,
            AccountOverviewReader,
            VolumeWindow,
        )

        overview = AccountOverview(
            perp_equity_balance=100.0,
            unrealized_pnl=5.0,
            unrealized_funding_cost=0.5,
            cross_margin_ratio=0.1,
            maintenance_margin=0.05,
            cross_account_leverage_ratio=None,
            volume=None,
            net_deposits=None,
            all_time_return=None,
            pnl_90d=None,
            sharpe_ratio=None,
            max_drawdown=None,
            weekly_win_rate_12w=None,
            average_cash_position=None,
            average_leverage=None,
            cross_account_position=10.0,
            total_margin=500.0,
            usdc_cross_withdrawable_balance=100.0,
            usdc_isolated_withdrawable_balance=0.0,
            realized_pnl=None,
            liquidation_fees_paid=None,
            liquidation_losses=None,
        )
        reader = AccountOverviewReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (overview, 200, "OK")
            await reader.get_by_addr(
                sub_addr="0xuser",
                volume_window=VolumeWindow.SEVEN_DAYS,
                include_performance=True,
            )

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["volume_window"] == "7d"
        assert call_kwargs["params"]["include_performance"] == "true"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._account_overview import AccountOverviewReader, AccountOverviewWsMessage

        reader = AccountOverviewReader(reader_deps)
        on_data = MagicMock()

        reader_deps.ws.subscribe.return_value = MagicMock()
        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert "account_overview:0xuser" in call_args[0][0]
        assert call_args[0][1] is AccountOverviewWsMessage


# ---------------------------------------------------------------------------
# CandlesticksReader
# ---------------------------------------------------------------------------


class TestCandlesticksReader:
    async def test_get_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._candlesticks import (
            Candlestick,
            CandlestickInterval,
            CandlesticksReader,
            _CandlesticksList,
        )

        candle = Candlestick(T=2000, c=100.0, h=105.0, i="1m", l=95.0, o=98.0, t=1000, v=500.0)
        candles_list = _CandlesticksList([candle])
        reader = CandlesticksReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (candles_list, 200, "OK")
            result = await reader.get_by_name(
                "BTC-PERP",
                interval=CandlestickInterval.ONE_MINUTE,
                start_time=1000,
                end_time=2000,
            )

        assert len(result) == 1
        assert result[0].close == 100.0

    def test_subscribe_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._candlesticks import (
            CandlestickInterval,
            CandlesticksReader,
            CandlestickWsMessage,
        )

        reader = CandlesticksReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_name("BTC-PERP", CandlestickInterval.ONE_MINUTE, on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert "1m" in call_args[0][0]
        assert call_args[0][1] is CandlestickWsMessage


# ---------------------------------------------------------------------------
# DelegationsReader
# ---------------------------------------------------------------------------


class TestDelegationsReader:
    async def test_get_all(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._delegations import Delegation, DelegationsReader, _DelegationsList

        delegation = Delegation(
            delegated_account="0xdeleg",
            permission_type="full",
            expiration_time_s=None,
        )
        delegations_list = _DelegationsList([delegation])
        reader = DelegationsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (delegations_list, 200, "OK")
            result = await reader.get_all(sub_addr="0xuser")

        assert len(result) == 1
        assert result[0].delegated_account == "0xdeleg"
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["subaccount"] == "0xuser"


# ---------------------------------------------------------------------------
# LeaderboardReader
# ---------------------------------------------------------------------------


class TestLeaderboardReader:
    async def test_get_leaderboard_no_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._leaderboard import LeaderboardReader, LeaderboardResponse

        response = LeaderboardResponse(items=[], total_count=0)
        reader = LeaderboardReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_leaderboard()

        assert result is response
        # params=None when no params provided
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"] is None

    async def test_get_leaderboard_with_all_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._leaderboard import LeaderboardReader, LeaderboardResponse

        response = LeaderboardResponse(items=[], total_count=0)
        reader = LeaderboardReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_leaderboard(
                limit=10,
                offset=5,
                search_term="0xuser",
                sort_key="volume",
                sort_dir="DESC",
            )

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["limit"] == "10"
        assert params["offset"] == "5"
        assert params["search_term"] == "0xuser"
        assert params["sort_key"] == "volume"
        assert params["sort_dir"] == "DESC"


# ---------------------------------------------------------------------------
# MarketContextsReader
# ---------------------------------------------------------------------------


class TestMarketContextsReader:
    async def test_get_all(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_contexts import (
            MarketContext,
            MarketContextsReader,
            _MarketContextList,
        )

        ctx = MarketContext(
            market="0xmarket",
            volume_24h=1000.0,
            open_interest=500.0,
            previous_day_price=100.0,
            price_change_pct_24h=1.5,
        )
        ctx_list = _MarketContextList([ctx])
        reader = MarketContextsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (ctx_list, 200, "OK")
            result = await reader.get_all()

        assert len(result) == 1
        assert result[0].market == "0xmarket"


# ---------------------------------------------------------------------------
# MarketDepthReader
# ---------------------------------------------------------------------------


class TestMarketDepthReader:
    async def test_get_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepth, MarketDepthReader

        depth = MarketDepth(market="0xmarket", bids=[], asks=[], unix_ms=1000)
        reader = MarketDepthReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (depth, 200, "OK")
            result = await reader.get_by_name("BTC-PERP")

        assert result is depth

    async def test_get_by_name_with_limit(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepth, MarketDepthReader

        depth = MarketDepth(market="0xmarket", bids=[], asks=[], unix_ms=1000)
        reader = MarketDepthReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (depth, 200, "OK")
            await reader.get_by_name("BTC-PERP", limit=5)

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["limit"] == "5"

    def test_subscribe_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepth, MarketDepthReader

        reader = MarketDepthReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_name("BTC-PERP", 1, on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert ":1" in call_args[0][0]  # aggregation_size in topic
        assert call_args[0][1] is MarketDepth

    def test_reset_subscription_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader(reader_deps)
        reader.reset_subscription_by_name("BTC-PERP", aggregation_size=5)
        reader_deps.ws.reset.assert_called_once()

    def test_get_aggregation_sizes(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader(reader_deps)
        sizes = reader.get_aggregation_sizes()
        assert sizes == (1, 2, 5, 10, 100, 1000)


# ---------------------------------------------------------------------------
# MarketPricesReader
# ---------------------------------------------------------------------------


class TestMarketPricesReader:
    async def test_get_all(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_prices import MarketPrice, MarketPricesReader, _MarketPriceList

        price = MarketPrice(
            market="0xmarket",
            mark_px=100.0,
            mid_px=99.9,
            oracle_px=100.1,
            funding_rate_bps=0.01,
            is_funding_positive=True,
            open_interest=5000.0,
            transaction_unix_ms=1000,
        )
        prices_list = _MarketPriceList([price])
        reader = MarketPricesReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (prices_list, 200, "OK")
            result = await reader.get_all()

        assert len(result) == 1

    async def test_get_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_prices import MarketPrice, MarketPricesReader, _MarketPriceList

        price = MarketPrice(
            market="0xmarket",
            mark_px=100.0,
            mid_px=99.9,
            oracle_px=100.1,
            funding_rate_bps=0.01,
            is_funding_positive=True,
            open_interest=5000.0,
            transaction_unix_ms=1000,
        )
        prices_list = _MarketPriceList([price])
        reader = MarketPricesReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (prices_list, 200, "OK")
            result = await reader.get_by_name("BTC-PERP")

        assert len(result) == 1

    def test_subscribe_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_prices import MarketPricesReader, MarketPriceWsMessage

        reader = MarketPricesReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_name("BTC-PERP", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert "market_price:" in call_args[0][0]
        assert call_args[0][1] is MarketPriceWsMessage

    def test_subscribe_by_address(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_prices import MarketPricesReader

        reader = MarketPricesReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_address("0xmarket", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "market_price:0xmarket"

    def test_subscribe_all(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_prices import AllMarketPricesWsMessage, MarketPricesReader

        reader = MarketPricesReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_all(on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "all_market_prices"
        assert call_args[0][1] is AllMarketPricesWsMessage


# ---------------------------------------------------------------------------
# MarketTradesReader
# ---------------------------------------------------------------------------


class TestMarketTradesReader:
    async def test_get_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_trades import (
            MarketTrade,
            MarketTradesReader,
            MarketTradesResponse,
        )

        trade = MarketTrade(
            account="0xaccount",
            market="0xmarket",
            action="OpenLong",
            trade_id="trade-1",
            size=1.0,
            price=100.0,
            is_profit=True,
            realized_pnl_amount=5.0,
            realized_funding_amount=0.1,
            is_rebate=False,
            fee_amount=0.05,
            order_id="order-1",
            client_order_id="client-1",
            source="taker",
            transaction_unix_ms=1000,
            transaction_version=1,
        )
        response = MarketTradesResponse(items=[trade], total_count=1)
        reader = MarketTradesReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_name("BTC-PERP")

        assert len(result) == 1

    async def test_get_by_name_with_limit(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_trades import MarketTradesReader, MarketTradesResponse

        response = MarketTradesResponse(items=[], total_count=0)
        reader = MarketTradesReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_by_name("BTC-PERP", limit=5)

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["limit"] == "5"

    def test_subscribe_by_name(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_trades import MarketTradesReader, MarketTradeWsMessage

        reader = MarketTradesReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_name("BTC-PERP", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert "trades:" in call_args[0][0]
        assert call_args[0][1] is MarketTradeWsMessage


# ---------------------------------------------------------------------------
# MarketsReader
# ---------------------------------------------------------------------------


class TestMarketsReader:
    async def test_get_all_deduplicates(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._markets import MarketsReader, PerpMarket, _PerpMarketList

        market = PerpMarket(
            market_addr="0xmarket",
            market_name="BTC-PERP",
            sz_decimals=2,
            px_decimals=2,
            max_leverage=10.0,
            tick_size=0.1,
            min_size=0.01,
            lot_size=0.01,
            max_open_interest=1000.0,
            mode="Open",
        )
        # Duplicate market
        markets_list = _PerpMarketList([market, market])
        reader = MarketsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (markets_list, 200, "OK")
            result = await reader.get_all()

        assert len(result) == 1
        assert result[0].market_addr == "0xmarket"

    async def test_get_by_name_success(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._markets import MarketsReader

        mock_resource = {
            "__variant__": "V1",
            "name": "BTC-PERP",
            "sz_precision": {"decimals": 2, "multiplier": "100"},
            "min_size": "1",
            "lot_size": "1",
            "ticker_size": "1",
            "max_leverage": 10.0,
            "mode": {"__variant__": "Open"},
        }
        reader_deps.aptos.account_resource = AsyncMock(return_value=mock_resource)
        reader = MarketsReader(reader_deps)

        result = await reader.get_by_name("BTC-PERP")

        assert result is not None
        assert result.name == "BTC-PERP"

    async def test_get_by_name_returns_none_on_error(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._markets import MarketsReader

        reader_deps.aptos.account_resource = AsyncMock(side_effect=Exception("resource not found"))
        reader = MarketsReader(reader_deps)

        result = await reader.get_by_name("NONEXISTENT-PERP")

        assert result is None

    async def test_list_market_addresses(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._markets import MarketsReader

        addresses = ["0xaddr1", "0xaddr2"]
        raw_bytes = json.dumps([addresses]).encode("utf-8")
        reader_deps.aptos.view = AsyncMock(return_value=raw_bytes)
        reader = MarketsReader(reader_deps)

        result = await reader.list_market_addresses()

        assert result == ["0xaddr1", "0xaddr2"]

    async def test_market_name_by_address(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._markets import MarketsReader

        raw_bytes = json.dumps(["BTC-PERP"]).encode("utf-8")
        reader_deps.aptos.view = AsyncMock(return_value=raw_bytes)
        reader = MarketsReader(reader_deps)

        result = await reader.market_name_by_address("0xmarket")

        assert result == "BTC-PERP"


# ---------------------------------------------------------------------------
# PortfolioChartReader
# ---------------------------------------------------------------------------


class TestPortfolioChartReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._portfolio_chart import (
            PortfolioChartItem,
            PortfolioChartReader,
            _PortfolioChartList,
        )

        item = PortfolioChartItem(timestamp=1000, data_points=50.0)
        chart_list = _PortfolioChartList([item])
        reader = PortfolioChartReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (chart_list, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser", time_range="7d", data_type="pnl")

        assert len(result) == 1
        assert result[0].data_points == 50.0
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert params["range"] == "7d"
        assert params["data_type"] == "pnl"


# ---------------------------------------------------------------------------
# TradingPointsReader
# ---------------------------------------------------------------------------


class TestTradingPointsReader:
    async def test_get_by_owner(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._trading_points import OwnerTradingPoints, TradingPointsReader

        points = OwnerTradingPoints(owner="0xowner", total_points=100.0, breakdown=None)
        reader = TradingPointsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (points, 200, "OK")
            result = await reader.get_by_owner(owner_addr="0xowner")

        assert result is points
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["owner"] == "0xowner"


# ---------------------------------------------------------------------------
# UserActiveTwapsReader
# ---------------------------------------------------------------------------


class TestUserActiveTwapsReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_active_twaps import (
            UserActiveTwap,
            UserActiveTwapsReader,
            _UserActiveTwapsList,
        )

        twap = UserActiveTwap(
            market="0xmarket",
            is_buy=True,
            order_id="0xorder",
            client_order_id="0xclient",
            is_reduce_only=False,
            start_unix_ms=1000,
            frequency_s=60,
            duration_s=3600,
            orig_size=1.0,
            remaining_size=0.5,
            status="Activated",
            transaction_unix_ms=1000,
            transaction_version=1,
        )
        twaps_list = _UserActiveTwapsList([twap])
        reader = UserActiveTwapsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (twaps_list, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert len(result) == 1
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["account"] == "0xuser"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_active_twaps import UserActiveTwapsReader, UserActiveTwapsWsMessage

        reader = UserActiveTwapsReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "user_active_twaps:0xuser"
        assert call_args[0][1] is UserActiveTwapsWsMessage


# ---------------------------------------------------------------------------
# UserBulkOrdersReader
# ---------------------------------------------------------------------------


class TestUserBulkOrdersReader:
    def test_previous_seq_num_is_optional(self) -> None:
        """Absent on API versions predating the field, and null on rejection rows."""
        from decibel.read._user_bulk_orders import UserBulkOrder

        order = UserBulkOrder.model_validate(
            {
                "market": "0xmarket",
                "sequence_number": 1,
                "bid_prices": [],
                "bid_sizes": [],
                "ask_prices": [],
                "ask_sizes": [],
                "cancelled_bid_prices": [],
                "cancelled_bid_sizes": [],
                "cancelled_ask_prices": [],
                "cancelled_ask_sizes": [],
            }
        )
        assert order.previous_seq_num is None

    async def test_get_by_addr_no_market(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_bulk_orders import (
            UserBulkOrder,
            UserBulkOrdersReader,
            _UserBulkOrdersList,
        )

        order = UserBulkOrder(
            market="0xmarket",
            sequence_number=1,
            previous_seq_num=0,
            bid_prices=[100.0],
            bid_sizes=[1.0],
            ask_prices=[101.0],
            ask_sizes=[1.0],
            cancelled_bid_prices=[],
            cancelled_bid_sizes=[],
            cancelled_ask_prices=[],
            cancelled_ask_sizes=[],
        )
        orders_list = _UserBulkOrdersList([order])
        reader = UserBulkOrdersReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (orders_list, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert len(result) == 1
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["account"] == "0xuser"
        assert call_kwargs["params"]["market"] == "all"

    async def test_get_by_addr_with_market(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_bulk_orders import UserBulkOrdersReader, _UserBulkOrdersList

        orders_list = _UserBulkOrdersList([])
        reader = UserBulkOrdersReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (orders_list, 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser", market="0xmarket")

        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["market"] == "0xmarket"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_bulk_orders import UserBulkOrdersReader, UserBulkOrderWsMessage

        reader = UserBulkOrdersReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "bulk_orders:0xuser"
        assert call_args[0][1] is UserBulkOrderWsMessage


# ---------------------------------------------------------------------------
# UserFundHistoryReader
# ---------------------------------------------------------------------------


class TestUserFundHistoryReader:
    async def test_get_by_addr_defaults(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_fund_history import UserFundHistoryReader, UserFundHistoryResponse

        response = UserFundHistoryResponse(funds=[], total=0)
        reader = UserFundHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert params["limit"] == "200"
        assert params["offset"] == "0"

    async def test_get_by_addr_custom_pagination(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_fund_history import UserFundHistoryReader, UserFundHistoryResponse

        response = UserFundHistoryResponse(funds=[], total=0)
        reader = UserFundHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser", limit=50, offset=100)

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["limit"] == "50"
        assert params["offset"] == "100"


# ---------------------------------------------------------------------------
# UserFundingHistoryReader
# ---------------------------------------------------------------------------


class TestUserFundingHistoryReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_funding_history import (
            UserFundingHistoryReader,
            UserFundingHistoryResponse,
        )

        response = UserFundingHistoryResponse(items=[], total_count=0)
        reader = UserFundingHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser", limit=20, offset=10)

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert params["limit"] == "20"
        assert params["offset"] == "10"


# ---------------------------------------------------------------------------
# UserNotificationsReader
# ---------------------------------------------------------------------------


class TestUserNotificationsReader:
    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_notifications import (
            UserNotificationsReader,
            UserNotificationWsMessage,
        )

        reader = UserNotificationsReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "notifications:0xuser"
        assert call_args[0][1] is UserNotificationWsMessage


# ---------------------------------------------------------------------------
# UserOpenOrdersReader
# ---------------------------------------------------------------------------


class TestUserOpenOrdersReader:
    async def test_get_by_addr_defaults(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersResponse

        response = UserOpenOrdersResponse(items=[], total_count=0)
        reader = UserOpenOrdersReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert "limit" not in params
        assert "offset" not in params

    async def test_get_by_addr_with_pagination(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersResponse

        response = UserOpenOrdersResponse(items=[], total_count=0)
        reader = UserOpenOrdersReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser", limit=10, offset=5)

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["limit"] == "10"
        assert params["offset"] == "5"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersWsMessage

        reader = UserOpenOrdersReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "account_open_orders:0xuser"
        assert call_args[0][1] is UserOpenOrdersWsMessage


# ---------------------------------------------------------------------------
# UserOrderHistoryReader
# ---------------------------------------------------------------------------


class TestUserOrderHistoryReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_order_history import UserOrderHistoryReader, UserOrders

        response = UserOrders(items=[], total_count=0)
        reader = UserOrderHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"

    async def test_get_by_addr_with_pagination(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_order_history import UserOrderHistoryReader, UserOrders

        response = UserOrders(items=[], total_count=0)
        reader = UserOrderHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser", limit=25, offset=50)

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["limit"] == "25"
        assert params["offset"] == "50"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_order_history import UserOrderHistoryReader, UserOrdersWsMessage

        reader = UserOrderHistoryReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "order_updates:0xuser"
        assert call_args[0][1] is UserOrdersWsMessage


# ---------------------------------------------------------------------------
# UserPositionsReader
# ---------------------------------------------------------------------------


class TestUserPositionsReader:
    async def test_get_by_addr_defaults(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_positions import UserPositionsReader, _UserPositionsList

        positions_list = _UserPositionsList([])
        reader = UserPositionsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (positions_list, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result == []
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert params["include_deleted"] == "false"
        assert params["limit"] == "10"

    async def test_get_by_addr_with_market_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_positions import UserPositionsReader, _UserPositionsList

        positions_list = _UserPositionsList([])
        reader = UserPositionsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (positions_list, 200, "OK")
            await reader.get_by_addr(
                sub_addr="0xuser", market_addr="0xmarket", include_deleted=True
            )

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["market_address"] == "0xmarket"
        assert params["include_deleted"] == "true"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_positions import UserPositionsReader, UserPositionsWsMessage

        reader = UserPositionsReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "account_positions:0xuser"
        assert call_args[0][1] is UserPositionsWsMessage


# ---------------------------------------------------------------------------
# UserSubaccountsReader
# ---------------------------------------------------------------------------


class TestUserSubaccountsReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_subaccounts import (
            UserSubaccount,
            UserSubaccountsReader,
            _UserSubaccountsList,
        )

        sub = UserSubaccount(
            subaccount_address="0xsub",
            primary_account_address="0xprimary",
            is_primary=True,
            is_active=True,
            custom_label=None,
        )
        subs_list = _UserSubaccountsList([sub])
        reader = UserSubaccountsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (subs_list, 200, "OK")
            result = await reader.get_by_addr(owner_addr="0xowner")

        assert len(result) == 1
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["owner"] == "0xowner"


# ---------------------------------------------------------------------------
# UserTradeHistoryReader
# ---------------------------------------------------------------------------


class TestUserTradeHistoryReader:
    async def test_get_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_trade_history import UserTradeHistoryReader, UserTradesResponse

        response = UserTradesResponse(items=[], total_count=0)
        reader = UserTradeHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser", limit=5, offset=10)

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert params["limit"] == "5"
        assert params["offset"] == "10"

    def test_subscribe_by_addr(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_trade_history import UserTradeHistoryReader, UserTradesWsMessage

        reader = UserTradeHistoryReader(reader_deps)
        on_data = MagicMock()
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", on_data)

        reader_deps.ws.subscribe.assert_called_once()
        call_args = reader_deps.ws.subscribe.call_args
        assert call_args[0][0] == "user_trades:0xuser"
        assert call_args[0][1] is UserTradesWsMessage


# ---------------------------------------------------------------------------
# UserTwapHistoryReader
# ---------------------------------------------------------------------------


class TestUserTwapHistoryReader:
    async def test_get_by_addr_defaults(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_twap_history import UserTwapHistoryReader, UserTwapHistoryResponse

        response = UserTwapHistoryResponse(items=[], total_count=0)
        reader = UserTwapHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_by_addr(sub_addr="0xuser")

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xuser"
        assert params["limit"] == "100"
        assert params["offset"] == "0"

    async def test_get_by_addr_custom(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_twap_history import UserTwapHistoryReader, UserTwapHistoryResponse

        response = UserTwapHistoryResponse(items=[], total_count=0)
        reader = UserTwapHistoryReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser", limit=25, offset=50)

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["limit"] == "25"
        assert params["offset"] == "50"


# ---------------------------------------------------------------------------
# VaultsReader
# ---------------------------------------------------------------------------


class TestVaultsReader:
    async def test_get_vaults_no_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._vaults import VaultsReader, VaultsResponse

        response = VaultsResponse(items=[], total_count=0, total_value_locked=0.0, total_volume=0.0)
        reader = VaultsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_vaults()

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"] is None

    async def test_get_vaults_with_all_params(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._vaults import VaultsReader, VaultsResponse

        response = VaultsResponse(items=[], total_count=0, total_value_locked=0.0, total_volume=0.0)
        reader = VaultsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_vaults(
                vault_type="user",
                limit=10,
                offset=5,
                address="0xvault",
                search="my vault",
            )

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["vault_type"] == "user"
        assert params["limit"] == "10"
        assert params["offset"] == "5"
        assert params["vault_address"] == "0xvault"
        assert params["search"] == "my vault"

    async def test_get_user_owned_vaults(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._vaults import UserOwnedVaultsResponse, VaultsReader

        response = UserOwnedVaultsResponse(items=[], total_count=0)
        reader = VaultsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            result = await reader.get_user_owned_vaults(owner_addr="0xowner")

        assert result is response
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["account"] == "0xowner"

    async def test_get_user_owned_vaults_with_pagination(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._vaults import UserOwnedVaultsResponse, VaultsReader

        response = UserOwnedVaultsResponse(items=[], total_count=0)
        reader = VaultsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (response, 200, "OK")
            await reader.get_user_owned_vaults(owner_addr="0xowner", limit=5, offset=10)

        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs["params"]
        assert params["limit"] == "5"
        assert params["offset"] == "10"

    async def test_get_user_performances_on_vaults(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._vaults import VaultsReader, _UserPerformancesOnVaultsList

        perfs_list = _UserPerformancesOnVaultsList([])
        reader = VaultsReader(reader_deps)

        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (perfs_list, 200, "OK")
            result = await reader.get_user_performances_on_vaults(owner_addr="0xowner")

        assert result == []
        call_kwargs = mock_req.call_args.kwargs
        assert call_kwargs["params"]["account"] == "0xowner"

    async def test_get_vault_share_price_normal(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._vaults import VaultsReader

        nav_bytes = json.dumps([1000]).encode("utf-8")
        shares_bytes = json.dumps([100]).encode("utf-8")
        reader_deps.aptos.view = AsyncMock(side_effect=[nav_bytes, shares_bytes])
        reader = VaultsReader(reader_deps)

        result = await reader.get_vault_share_price(vault_address="0xvault")

        assert result == pytest.approx(10.0)

    async def test_get_vault_share_price_zero_shares_returns_1(
        self, reader_deps: ReaderDeps
    ) -> None:
        from decibel.read._vaults import VaultsReader

        nav_bytes = json.dumps([0]).encode("utf-8")
        shares_bytes = json.dumps([0]).encode("utf-8")
        reader_deps.aptos.view = AsyncMock(side_effect=[nav_bytes, shares_bytes])
        reader = VaultsReader(reader_deps)

        result = await reader.get_vault_share_price(vault_address="0xvault")

        assert result == 1.0

    async def test_get_vault_share_price_on_exception_returns_1(
        self, reader_deps: ReaderDeps
    ) -> None:
        from decibel.read._vaults import VaultsReader

        reader_deps.aptos.view = AsyncMock(side_effect=Exception("aptos error"))
        reader = VaultsReader(reader_deps)

        result = await reader.get_vault_share_price(vault_address="0xvault")

        assert result == 1.0


# ---------------------------------------------------------------------------
# URL construction checks (spot-check a few readers)
# ---------------------------------------------------------------------------


class TestUrlConstruction:
    async def test_account_overview_url(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._account_overview import AccountOverview, AccountOverviewReader

        overview = AccountOverview(
            perp_equity_balance=0.0,
            unrealized_pnl=0.0,
            unrealized_funding_cost=0.0,
            cross_margin_ratio=0.0,
            maintenance_margin=0.0,
            cross_account_leverage_ratio=None,
            volume=None,
            net_deposits=None,
            all_time_return=None,
            pnl_90d=None,
            sharpe_ratio=None,
            max_drawdown=None,
            weekly_win_rate_12w=None,
            average_cash_position=None,
            average_leverage=None,
            cross_account_position=0.0,
            total_margin=0.0,
            usdc_cross_withdrawable_balance=0.0,
            usdc_isolated_withdrawable_balance=0.0,
            realized_pnl=None,
            liquidation_fees_paid=None,
            liquidation_losses=None,
        )
        reader = AccountOverviewReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (overview, 200, "OK")
            await reader.get_by_addr(sub_addr="0xuser")
        call_args = mock_req.call_args
        # URL is the second positional arg or 'url' kwarg
        url_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "/api/v1/account_overviews" in url_arg

    async def test_market_contexts_url(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_contexts import MarketContextsReader, _MarketContextList

        ctx_list = _MarketContextList([])
        reader = MarketContextsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (ctx_list, 200, "OK")
            await reader.get_all()
        call_args = mock_req.call_args
        url_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "/api/v1/asset_contexts" in url_arg

    async def test_trading_points_url(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._trading_points import OwnerTradingPoints, TradingPointsReader

        pts = OwnerTradingPoints(owner="0xowner", total_points=0.0, breakdown=None)
        reader = TradingPointsReader(reader_deps)
        with patch.object(reader, "get_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (pts, 200, "OK")
            await reader.get_by_owner(owner_addr="0xowner")
        call_args = mock_req.call_args
        url_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("url", "")
        assert "/api/v1/points/trading/account" in url_arg
