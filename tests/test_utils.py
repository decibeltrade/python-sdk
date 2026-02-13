from __future__ import annotations

from decibel import (
    amount_to_chain_units,
    chain_units_to_amount,
    round_to_tick_size,
    round_to_valid_order_size,
    round_to_valid_price,
)


class TestAmountToChainUnits:
    def test_basic_conversion(self) -> None:
        assert amount_to_chain_units(5.67) == 5670000

    def test_zero(self) -> None:
        assert amount_to_chain_units(0) == 0

    def test_whole_number(self) -> None:
        assert amount_to_chain_units(100) == 100000000

    def test_custom_decimals(self) -> None:
        assert amount_to_chain_units(1.5, decimals=8) == 150000000

    def test_small_amount(self) -> None:
        assert amount_to_chain_units(0.000001) == 1


class TestChainUnitsToAmount:
    def test_basic_conversion(self) -> None:
        assert chain_units_to_amount(5670000) == 5.67

    def test_zero(self) -> None:
        assert chain_units_to_amount(0) == 0.0

    def test_whole_number(self) -> None:
        assert chain_units_to_amount(100000000) == 100.0

    def test_custom_decimals(self) -> None:
        assert chain_units_to_amount(150000000, decimals=8) == 1.5

    def test_small_amount(self) -> None:
        assert chain_units_to_amount(1) == 0.000001


class TestRoundToValidPrice:
    def test_exact_tick(self) -> None:
        result = round_to_valid_price(100.0, tick_size=100, px_decimals=2)
        assert result == 100.0

    def test_round_down(self) -> None:
        result = round_to_valid_price(100.24, tick_size=100, px_decimals=2)
        assert result == 100.0

    def test_round_up(self) -> None:
        result = round_to_valid_price(100.75, tick_size=100, px_decimals=2)
        assert result == 101.0

    def test_half_rounds_to_even(self) -> None:
        result = round_to_valid_price(100.50, tick_size=100, px_decimals=2)
        assert result == 100.0 or result == 101.0

    def test_zero_price(self) -> None:
        result = round_to_valid_price(0.0, tick_size=100, px_decimals=2)
        assert result == 0.0

    def test_large_tick_size(self) -> None:
        result = round_to_valid_price(97123.45, tick_size=1000, px_decimals=2)
        assert result == 97120.0


class TestRoundToValidOrderSize:
    def test_exact_lot(self) -> None:
        result = round_to_valid_order_size(1.0, lot_size=1000, sz_decimals=4, min_size=100)
        assert result == 1.0

    def test_round_to_lot(self) -> None:
        result = round_to_valid_order_size(1.05, lot_size=1000, sz_decimals=4, min_size=100)
        assert result == 1.0

    def test_round_up_to_lot(self) -> None:
        result = round_to_valid_order_size(1.08, lot_size=1000, sz_decimals=4, min_size=100)
        assert result == 1.1

    def test_below_min_returns_min(self) -> None:
        result = round_to_valid_order_size(0.005, lot_size=1000, sz_decimals=4, min_size=100)
        assert result == 0.01

    def test_zero_size(self) -> None:
        result = round_to_valid_order_size(0.0, lot_size=1000, sz_decimals=4, min_size=100)
        assert result == 0.0

    def test_exactly_min_size(self) -> None:
        result = round_to_valid_order_size(0.01, lot_size=100, sz_decimals=4, min_size=100)
        assert result == 0.01


class TestRoundToTickSize:
    def test_round_up(self) -> None:
        result = round_to_tick_size(100.24, tick_size=100, px_decimals=2, round_up=True)
        assert result == 101.0

    def test_round_down(self) -> None:
        result = round_to_tick_size(100.99, tick_size=100, px_decimals=2, round_up=False)
        assert result == 100.0

    def test_zero_price(self) -> None:
        result = round_to_tick_size(0.0, tick_size=100, px_decimals=2, round_up=True)
        assert result == 0.0
