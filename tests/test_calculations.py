"""Tests for decibel._calculations (liquidation price), ported from the TS SDK."""

from __future__ import annotations

import pytest

from decibel._calculations import (
    LiquidationMarket,
    LiquidationMarketContext,
    LiquidationPosition,
    LiquidationPriceInput,
    calculate_liquidation_price,
)


def _make_input(**overrides: object) -> LiquidationPriceInput:
    base: dict[str, object] = {
        "account_equity": 100.0,
        "positions": [],
        "markets": [LiquidationMarket("0xBTC", "BTC/USD", 10)],
        "market_contexts": [LiquidationMarketContext("BTC/USD", 100)],
        "target_market_addr": "0xBTC",
        "order_size": 1,
        "execution_price": 100,
    }
    base.update(overrides)
    return LiquidationPriceInput(**base)  # type: ignore[arg-type]


class TestCalculateLiquidationPrice:
    def test_long_below_mark(self) -> None:
        result = calculate_liquidation_price(_make_input(account_equity=50, order_size=5))
        assert result == pytest.approx(94.736843, abs=1e-5)

    def test_short_above_mark(self) -> None:
        result = calculate_liquidation_price(_make_input(order_size=-1))
        assert result == pytest.approx(190.47619, abs=1e-4)

    def test_zero_buffer_returns_mark(self) -> None:
        assert calculate_liquidation_price(_make_input(account_equity=5)) == 100

    def test_negative_buffer_returns_mark(self) -> None:
        assert calculate_liquidation_price(_make_input(account_equity=1)) == 100

    def test_closing_position_returns_zero(self) -> None:
        result = calculate_liquidation_price(
            _make_input(
                positions=[LiquidationPosition("0xBTC", 1, 100)],
                order_size=-1,
            )
        )
        assert result == 0

    def test_clamps_to_zero(self) -> None:
        assert calculate_liquidation_price(_make_input(account_equity=100000)) == 0

    def test_direction_flip_long_to_short(self) -> None:
        result = calculate_liquidation_price(
            _make_input(
                positions=[LiquidationPosition("0xBTC", 3, 95)],
                order_size=-8,
                execution_price=105,
            )
        )
        assert result == pytest.approx(121.904761, abs=1e-5)

    def test_direction_flip_short_to_long(self) -> None:
        result = calculate_liquidation_price(
            _make_input(
                positions=[LiquidationPosition("0xBTC", -3, 105)],
                order_size=8,
                execution_price=95,
            )
        )
        assert result == pytest.approx(75.789474, abs=1e-5)

    def test_partial_reduction_keeps_entry(self) -> None:
        result = calculate_liquidation_price(
            _make_input(
                positions=[LiquidationPosition("0xBTC", 10, 90)],
                order_size=-3,
                execution_price=110,
            )
        )
        assert result == pytest.approx(85.714286, abs=1e-5)

    def test_raises_when_market_missing(self) -> None:
        with pytest.raises(ValueError, match="Market not found"):
            calculate_liquidation_price(_make_input(target_market_addr="0xNONE"))

    def test_raises_when_no_position_and_zero_order(self) -> None:
        with pytest.raises(ValueError, match="No position found"):
            calculate_liquidation_price(_make_input(order_size=0))

    def test_raises_on_invalid_max_leverage(self) -> None:
        with pytest.raises(ValueError, match="Invalid max_leverage"):
            calculate_liquidation_price(
                _make_input(markets=[LiquidationMarket("0xBTC", "BTC/USD", 0)])
            )


class TestCalculateLiquidationPriceExtra:
    def test_size_increase_uses_vwap_entry(self) -> None:
        # Existing +2 @100, add +2 @110 -> net +4, VWAP entry = 105.
        result = calculate_liquidation_price(
            _make_input(
                positions=[LiquidationPosition("0xBTC", 2, 100)],
                order_size=2,
                execution_price=110,
            )
        )
        assert result == pytest.approx(84.210527, abs=1e-5)

    def test_multi_position_adds_maintenance_margin(self) -> None:
        # An ETH position contributes maintenance margin against the BTC liq price.
        result = calculate_liquidation_price(
            _make_input(
                positions=[LiquidationPosition("0xETH", 2, 50)],
                markets=[
                    LiquidationMarket("0xBTC", "BTC/USD", 10),
                    LiquidationMarket("0xETH", "ETH/USD", 5),
                ],
                market_contexts=[
                    LiquidationMarketContext("BTC/USD", 100),
                    LiquidationMarketContext("ETH/USD", 50),
                ],
                order_size=5,
            )
        )
        assert result == pytest.approx(86.31579, abs=1e-5)

    def test_raises_when_market_context_missing(self) -> None:
        with pytest.raises(ValueError, match="Market context not found"):
            calculate_liquidation_price(
                _make_input(market_contexts=[LiquidationMarketContext("OTHER", 100)])
            )
