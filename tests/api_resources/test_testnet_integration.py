"""Integration tests that run against the live Decibel testnet API.

These tests verify that the SDK correctly parses real API responses
and that the spec matches actual server behavior.

Run with:
    DECIBEL_API_KEY=<key> uv run pytest tests/api_resources/test_testnet_integration.py -v

Skip with:
    uv run pytest tests/api_resources/test_testnet_integration.py -v  (auto-skips without key)
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from decibel._constants import TESTNET_CONFIG
from decibel.read import DecibelReadDex

# ---------------------------------------------------------------------------
# Skip entire module if no API key
# ---------------------------------------------------------------------------

DECIBEL_API_KEY = os.environ.get("DECIBEL_API_KEY")

pytestmark = pytest.mark.skipif(
    not DECIBEL_API_KEY,
    reason="DECIBEL_API_KEY env var not set — skipping testnet integration tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def read() -> DecibelReadDex:
    """Shared read client for all tests in this module."""
    return DecibelReadDex(TESTNET_CONFIG, api_key=DECIBEL_API_KEY)


@pytest.fixture(scope="module")
def first_market_addr(read: DecibelReadDex) -> str:
    """Get a valid market address from testnet for parameterized tests."""
    markets = asyncio.get_event_loop().run_until_complete(read.markets.get_all())
    assert len(markets) > 0, "Testnet should have at least one market"
    return markets[0].market_addr


# ---------------------------------------------------------------------------
# SPEC-REST Section 2.2: GET /api/v1/markets
# ---------------------------------------------------------------------------


class TestMarketsIntegration:
    """Verify /api/v1/markets against live testnet."""

    async def test_get_all_markets_returns_list(self, read: DecibelReadDex) -> None:
        """SHALL return a non-empty list of PerpMarket objects."""
        markets = await read.markets.get_all()
        assert isinstance(markets, list)
        assert len(markets) > 0

    async def test_market_has_required_fields(self, read: DecibelReadDex) -> None:
        """Each market SHALL have all required MarketDto fields per spec."""
        markets = await read.markets.get_all()
        market = markets[0]

        # Required fields per SPEC-REST.md Section 11.6
        assert isinstance(market.market_addr, str)
        assert market.market_addr.startswith("0x")
        assert isinstance(market.market_name, str)
        assert len(market.market_name) > 0
        assert isinstance(market.sz_decimals, int)
        assert market.sz_decimals >= 0
        assert isinstance(market.px_decimals, int)
        assert market.px_decimals >= 0
        assert isinstance(market.max_leverage, (int, float))
        assert market.max_leverage > 0
        assert isinstance(market.tick_size, (int, float))
        assert market.tick_size > 0
        assert isinstance(market.min_size, (int, float))
        assert market.min_size > 0
        assert isinstance(market.lot_size, (int, float))
        assert market.lot_size > 0
        assert isinstance(market.max_open_interest, float)

    async def test_market_mode_is_valid(self, read: DecibelReadDex) -> None:
        """Market mode SHALL be one of the valid enum values."""
        from decibel.read._markets import MarketMode

        markets = await read.markets.get_all()
        valid_modes = {m.value for m in MarketMode}
        for market in markets:
            assert market.mode.value in valid_modes, (
                f"Market {market.market_name} has unexpected mode: {market.mode}"
            )

    async def test_market_addresses_are_unique(self, read: DecibelReadDex) -> None:
        """Each market SHALL have a unique address."""
        markets = await read.markets.get_all()
        addrs = [m.market_addr for m in markets]
        assert len(addrs) == len(set(addrs)), "Duplicate market addresses found"


# ---------------------------------------------------------------------------
# SPEC-REST Section 2.1: GET /api/v1/prices
# ---------------------------------------------------------------------------


class TestPricesIntegration:
    """Verify /api/v1/prices against live testnet."""

    async def test_get_all_prices(self, read: DecibelReadDex) -> None:
        """SHALL return prices for all markets."""
        prices = await read.market_prices.get_all()
        assert isinstance(prices, list)
        assert len(prices) > 0

    async def test_price_has_required_fields(self, read: DecibelReadDex) -> None:
        """Each price SHALL have all required PriceDto fields per spec."""
        prices = await read.market_prices.get_all()
        price = prices[0]

        # Required fields per SPEC-REST.md Section 11.1
        assert isinstance(price.market, str)
        assert price.market.startswith("0x")
        assert isinstance(price.oracle_px, float)
        assert price.oracle_px > 0
        assert isinstance(price.mark_px, float)
        assert isinstance(price.mid_px, float)
        assert isinstance(price.funding_rate_bps, float)
        assert isinstance(price.is_funding_positive, bool)
        assert isinstance(price.transaction_unix_ms, int)
        assert price.transaction_unix_ms > 0
        assert isinstance(price.open_interest, float)
        assert price.open_interest >= 0

    async def test_price_count_matches_markets(self, read: DecibelReadDex) -> None:
        """Number of prices SHOULD match number of markets."""
        markets = await read.markets.get_all()
        prices = await read.market_prices.get_all()
        assert len(prices) == len(markets), (
            f"Expected {len(markets)} prices, got {len(prices)}"
        )

    async def test_price_markets_match_market_list(self, read: DecibelReadDex) -> None:
        """Price market addresses SHALL be from the known market list."""
        markets = await read.markets.get_all()
        market_addrs = {m.market_addr for m in markets}
        prices = await read.market_prices.get_all()
        for price in prices:
            assert price.market in market_addrs, (
                f"Price for unknown market: {price.market}"
            )


# ---------------------------------------------------------------------------
# SPEC-REST Section 2.3: GET /api/v1/candlesticks
# ---------------------------------------------------------------------------


class TestCandlesticksIntegration:
    """Verify /api/v1/candlesticks against live testnet."""

    async def test_get_candlesticks(
        self, read: DecibelReadDex, first_market_addr: str
    ) -> None:
        """SHALL return candlestick data for a valid market and time range."""
        from decibel.read._candlesticks import CandlestickInterval

        now_ms = int(time.time() * 1000)
        candles = await read.candlesticks.get_by_name(
            # Use market name from first market
            market_name=(await read.markets.get_all())[0].market_name,
            interval=CandlestickInterval.ONE_DAY,
            start_time=now_ms - 86400000 * 30,  # 30 days ago
            end_time=now_ms,
        )
        # May be empty if no recent trades, but should not error
        assert isinstance(candles, list)

    async def test_candlestick_fields(self, read: DecibelReadDex) -> None:
        """Each candlestick SHALL have OHLCV fields per spec."""
        from decibel.read._candlesticks import CandlestickInterval

        markets = await read.markets.get_all()
        now_ms = int(time.time() * 1000)

        # Try all markets until we find one with candles
        candles = []
        for market in markets:
            candles = await read.candlesticks.get_by_name(
                market_name=market.market_name,
                interval=CandlestickInterval.ONE_DAY,
                start_time=now_ms - 86400000 * 90,
                end_time=now_ms,
            )
            if candles:
                break

        if not candles:
            pytest.skip("No candlestick data available on testnet")

        candle = candles[0]
        assert isinstance(candle.time_start, int)  # alias: t
        assert isinstance(candle.time_end, int)  # alias: T
        assert candle.time_end > candle.time_start
        assert isinstance(candle.open_price, float)  # alias: o
        assert isinstance(candle.high, float)  # alias: h
        assert isinstance(candle.low, float)  # alias: l
        assert isinstance(candle.close, float)  # alias: c
        assert isinstance(candle.volume, float)  # alias: v
        assert isinstance(candle.interval, str)  # alias: i
        assert candle.high >= candle.low


# ---------------------------------------------------------------------------
# SPEC-REST Section 2.5: GET /api/v1/asset_contexts
# ---------------------------------------------------------------------------


class TestAssetContextsIntegration:
    """Verify /api/v1/asset_contexts against live testnet."""

    async def test_get_all_contexts(self, read: DecibelReadDex) -> None:
        """SHALL return market contexts with 24h stats."""
        contexts = await read.market_contexts.get_all()
        assert isinstance(contexts, list)
        assert len(contexts) > 0

    async def test_context_has_required_fields(self, read: DecibelReadDex) -> None:
        """Each context SHALL have required AssetContextDto fields."""
        contexts = await read.market_contexts.get_all()
        ctx = contexts[0]

        # market field is the market name (e.g., "ETH/USD"), not address
        assert isinstance(ctx.market, str)
        assert len(ctx.market) > 0
        assert isinstance(ctx.volume_24h, float)
        assert isinstance(ctx.open_interest, float)
        assert isinstance(ctx.previous_day_price, float)
        assert isinstance(ctx.price_change_pct_24h, float)


# ---------------------------------------------------------------------------
# SPEC-REST Section 2.4: GET /api/v1/trades
# ---------------------------------------------------------------------------


class TestTradesIntegration:
    """Verify /api/v1/trades against live testnet."""

    async def test_get_market_trades(self, read: DecibelReadDex) -> None:
        """SHALL return a list of trades for a market."""
        markets = await read.markets.get_all()
        trades = await read.market_trades.get_by_name(
            market_name=markets[0].market_name,
            limit=5,
        )
        assert isinstance(trades, list)

    async def test_trade_has_required_fields(self, read: DecibelReadDex) -> None:
        """Each trade SHALL have all TradeDto fields per spec."""
        markets = await read.markets.get_all()

        # Try markets until we find one with trades
        trades: list = []
        for market in markets:
            trades = await read.market_trades.get_by_name(
                market_name=market.market_name, limit=2
            )
            if trades:
                break

        if not trades:
            pytest.skip("No trades available on testnet")

        trade = trades[0]
        assert isinstance(trade.account, str)
        assert trade.account.startswith("0x")
        assert isinstance(trade.market, str)
        assert isinstance(trade.action, str)
        assert isinstance(trade.trade_id, (str, int))
        assert isinstance(trade.size, float)
        assert trade.size > 0
        assert isinstance(trade.price, float)
        assert trade.price > 0
        assert isinstance(trade.is_profit, bool)
        assert isinstance(trade.realized_pnl_amount, float)
        assert isinstance(trade.fee_amount, float)
        assert isinstance(trade.order_id, str)
        assert isinstance(trade.transaction_unix_ms, int)
        assert isinstance(trade.transaction_version, int)


# ---------------------------------------------------------------------------
# SPEC-REST Section 8.1: GET /api/v1/leaderboard
# ---------------------------------------------------------------------------


class TestLeaderboardIntegration:
    """Verify /api/v1/leaderboard against live testnet."""

    async def test_get_leaderboard(self, read: DecibelReadDex) -> None:
        """SHALL return paginated leaderboard with total_count."""
        result = await read.leaderboard.get_leaderboard(limit=5, offset=0)
        assert hasattr(result, "items")
        assert hasattr(result, "total_count")
        assert result.total_count > 0

    async def test_leaderboard_entry_fields(self, read: DecibelReadDex) -> None:
        """Each entry SHALL have rank, account, account_value, realized_pnl, roi, volume."""
        result = await read.leaderboard.get_leaderboard(limit=3, offset=0)
        assert len(result.items) > 0

        entry = result.items[0]
        assert isinstance(entry.rank, int)
        assert entry.rank >= 0
        assert isinstance(entry.account, str)
        assert entry.account.startswith("0x")
        assert isinstance(entry.account_value, float)
        assert isinstance(entry.realized_pnl, float)
        assert isinstance(entry.roi, float)
        assert isinstance(entry.volume, float)

    async def test_leaderboard_pagination(self, read: DecibelReadDex) -> None:
        """Pagination SHALL work: offset=0 limit=2 then offset=2 limit=2."""
        page1 = await read.leaderboard.get_leaderboard(limit=2, offset=0)
        page2 = await read.leaderboard.get_leaderboard(limit=2, offset=2)

        if page1.total_count < 4:
            pytest.skip(f"Not enough leaderboard entries ({page1.total_count}) to test pagination")

        p1_accounts = {e.account for e in page1.items}
        p2_accounts = {e.account for e in page2.items}
        assert p1_accounts != p2_accounts, "Pagination returned same results for different offsets"


# ---------------------------------------------------------------------------
# SPEC-REST Section 7.1: GET /api/v1/vaults
# ---------------------------------------------------------------------------


class TestVaultsIntegration:
    """Verify /api/v1/vaults against live testnet."""

    async def test_get_public_vaults(self, read: DecibelReadDex) -> None:
        """SHALL return paginated vault listing."""
        result = await read.vaults.get_vaults(limit=5, offset=0)
        assert hasattr(result, "items")
        assert hasattr(result, "total_count")

    async def test_vault_has_required_fields(self, read: DecibelReadDex) -> None:
        """Each vault SHALL have core fields per spec."""
        result = await read.vaults.get_vaults(limit=2, offset=0)
        if not result.items:
            pytest.skip("No vaults on testnet")

        vault = result.items[0]
        assert isinstance(vault.address, str)
        assert vault.address.startswith("0x")
        assert isinstance(vault.name, str)
        assert isinstance(vault.status, str)


# ---------------------------------------------------------------------------
# WebSocket integration — quick smoke test
# ---------------------------------------------------------------------------


class TestWebSocketIntegration:
    """Verify WebSocket connection and subscription against live testnet."""

    async def test_subscribe_all_market_prices(self, read: DecibelReadDex) -> None:
        """SHALL receive at least one all_market_prices message within 15s."""
        received: list = []
        event = asyncio.Event()

        def on_data(msg: object) -> None:
            received.append(msg)
            event.set()

        unsub = read.market_prices.subscribe_all(on_data)

        try:
            # Wait up to 15 seconds for first message
            await asyncio.wait_for(event.wait(), timeout=15.0)
        except TimeoutError:
            pytest.skip("No WebSocket message received within 15s (testnet may be quiet)")
        finally:
            unsub()
            await read.ws.close()

        assert len(received) >= 1
        msg = received[0]
        # Type check: should be AllMarketPricesWsMessage
        from decibel.read._market_prices import AllMarketPricesWsMessage

        assert isinstance(msg, AllMarketPricesWsMessage)
        assert isinstance(msg.prices, list)
        assert len(msg.prices) > 0, "Expected at least one price in WS message"
        price = msg.prices[0]
        assert isinstance(price.market, str)
        assert isinstance(price.oracle_px, float)
        assert price.oracle_px > 0

    async def test_subscribe_market_price_single(self, read: DecibelReadDex) -> None:
        """SHALL receive price updates for a single market."""
        markets = await read.markets.get_all()
        if not markets:
            pytest.skip("No markets on testnet")

        received: list = []
        event = asyncio.Event()

        def on_data(msg: object) -> None:
            received.append(msg)
            event.set()

        unsub = read.market_prices.subscribe_by_address(
            markets[0].market_addr, on_data
        )

        try:
            await asyncio.wait_for(event.wait(), timeout=15.0)
        except TimeoutError:
            pytest.skip("No WebSocket message received within 15s")
        finally:
            unsub()
            await read.ws.close()

        assert len(received) >= 1
        msg = received[0]
        from decibel.read._market_prices import MarketPriceWsMessage

        assert isinstance(msg, MarketPriceWsMessage)
        assert msg.price.market == markets[0].market_addr
        assert isinstance(msg.price.oracle_px, float)
        assert msg.price.oracle_px > 0
