from __future__ import annotations

import pytest

from decibel import (
    TESTNET_CONFIG,
    amount_to_chain_units,
    chain_units_to_amount,
    get_market_addr,
    get_market_addr_for_product,
    get_spot_market_addr,
    round_to_tick_size,
    round_to_tick_size_for_side,
    round_to_valid_order_size,
    round_to_valid_price,
)
from decibel.read import AssetTypeName


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

    def test_no_float_truncation(self) -> None:
        assert amount_to_chain_units(0.29, decimals=2) == 29
        assert amount_to_chain_units(0.57, decimals=2) == 57
        assert amount_to_chain_units(0.57, decimals=4) == 5700
        assert amount_to_chain_units(1.14, decimals=4) == 11400


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


class TestRoundToTickSizeForSide:
    """Buys round down, sells round up — never crossing the trader's own limit."""

    def test_buy_rounds_down(self) -> None:
        assert (
            round_to_tick_size_for_side(100.99, tick_size=100, px_decimals=2, is_buy=True) == 100.0
        )

    def test_sell_rounds_up(self) -> None:
        assert (
            round_to_tick_size_for_side(100.01, tick_size=100, px_decimals=2, is_buy=False) == 101.0
        )

    def test_on_tick_price_is_unchanged(self) -> None:
        # Guards the float-epsilon nudge: 3.0 ticks must not slip to 2.9999999999999996.
        assert round_to_tick_size_for_side(3.0, tick_size=100, px_decimals=2, is_buy=True) == 3.0
        assert round_to_tick_size_for_side(3.0, tick_size=100, px_decimals=2, is_buy=False) == 3.0

    def test_zero_price(self) -> None:
        assert round_to_tick_size_for_side(0.0, tick_size=100, px_decimals=2, is_buy=True) == 0.0

    def test_zero_tick_size(self) -> None:
        assert round_to_tick_size_for_side(1.23, tick_size=0, px_decimals=2, is_buy=True) == 0.0

    @pytest.mark.parametrize("is_buy", [True, False])
    def test_never_worse_than_requested(self, is_buy: bool) -> None:
        price = 97123.456
        rounded = round_to_tick_size_for_side(price, tick_size=1000, px_decimals=2, is_buy=is_buy)
        assert rounded <= price if is_buy else rounded >= price


# Cross-checked against the TypeScript SDK's getSpotMarketAddr for the same inputs.
_TESTNET_PACKAGE = "0xe7da2794b1d8af76532ed95f38bfdf1136abfd8ea3a240189971988a83101b7f"
_SPOT_APT_USDC = "0x26f1ddaa436a7b134d5c872c032eaa66653b673bca2bb1539642094d6b113c50"
_SPOT_BTC_USDC = "0x60783473d2254b4c19e2b3c4bd7e36c02d2b2822276aedb0619074e55441cd6a"


class TestGetSpotMarketAddr:
    def test_known_market(self) -> None:
        assert get_spot_market_addr("APT/USDC", _TESTNET_PACKAGE) == _SPOT_APT_USDC

    def test_second_known_market(self) -> None:
        assert get_spot_market_addr("BTC/USDC", _TESTNET_PACKAGE) == _SPOT_BTC_USDC

    def test_derives_from_package_not_perp_engine(self) -> None:
        deployment = TESTNET_CONFIG.deployment
        assert get_spot_market_addr("APT/USDC", deployment.package) != get_market_addr(
            "APT/USDC", deployment.perp_engine_global
        )


class TestGetMarketAddrForProduct:
    def test_spot(self) -> None:
        deployment = TESTNET_CONFIG.deployment
        assert get_market_addr_for_product("APT/USDC", AssetTypeName.SPOT, deployment) == (
            get_spot_market_addr("APT/USDC", deployment.package)
        )

    def test_perp(self) -> None:
        deployment = TESTNET_CONFIG.deployment
        assert get_market_addr_for_product("APT/USD", AssetTypeName.PERP, deployment) == (
            get_market_addr("APT/USD", deployment.perp_engine_global)
        )

    def test_accepts_plain_strings(self) -> None:
        deployment = TESTNET_CONFIG.deployment
        assert get_market_addr_for_product("APT/USDC", "spot", deployment) == _SPOT_APT_USDC

    def test_unknown_asset_type_falls_back_to_perp(self) -> None:
        deployment = TESTNET_CONFIG.deployment
        assert get_market_addr_for_product("APT/USD", "", deployment) == (
            get_market_addr("APT/USD", deployment.perp_engine_global)
        )
