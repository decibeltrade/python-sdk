"""Tests for DecibelReadDex on-chain view / resource helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from decibel.read import DecibelReadDex
from decibel.read._types import CrossedPosition

if TYPE_CHECKING:
    from decibel._constants import DecibelConfig

# Reader attributes DecibelReadDex.__init__ must wire up.
_READER_ATTRS = (
    "account_overview",
    "candlesticks",
    "delegations",
    "leaderboard",
    "markets",
    "market_prices",
    "market_depth",
    "market_trades",
    "market_contexts",
    "portfolio_chart",
    "user_positions",
    "user_open_orders",
    "user_order_history",
    "user_trade_history",
    "user_bulk_orders",
    "user_subaccounts",
    "user_fund_history",
    "user_funding_history",
    "user_active_twaps",
    "user_twap_history",
    "user_notifications",
    "vaults",
    "trading_points",
    "campaigns",
    "points_leaderboard",
    "streaks",
    "trading_amps",
    "tier",
    "global_points_stats",
    "referrals",
    "user_fees",
    "withdraw_queue",
)


@pytest.fixture
def read_dex(test_config: DecibelConfig) -> DecibelReadDex:
    """A DecibelReadDex with only the attributes the view helpers need."""
    dex = DecibelReadDex.__new__(DecibelReadDex)
    dex._config = test_config
    dex._aptos = AsyncMock()
    dex._usdc_decimals_cache = None
    return dex


def _view_bytes(value: list[object]) -> bytes:
    return json.dumps(value).encode("utf-8")


class TestGlobalPerpEngineState:
    async def test_returns_resource(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.account_resource = AsyncMock(return_value={"foo": "bar"})
        result = await read_dex.global_perp_engine_state()
        assert result == {"foo": "bar"}
        call = read_dex._aptos.account_resource.call_args
        pkg = read_dex._config.deployment.package
        assert call.args[1] == f"{pkg}::perp_engine::Global"

    async def test_returns_false_on_error(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.account_resource = AsyncMock(side_effect=Exception("missing"))
        assert await read_dex.global_perp_engine_state() is False


class TestDecimalsAndBalances:
    async def test_collateral_balance_decimals(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.view = AsyncMock(return_value=_view_bytes([6]))
        assert await read_dex.collateral_balance_decimals() == 6

    async def test_usdc_decimals_is_cached(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.view = AsyncMock(return_value=_view_bytes([6]))
        assert await read_dex.usdc_decimals() == 6
        assert await read_dex.usdc_decimals() == 6
        # Cached: only one view call.
        read_dex._aptos.view.assert_awaited_once()

    async def test_usdc_balance_scales_by_decimals(self, read_dex: DecibelReadDex) -> None:
        read_dex._usdc_decimals_cache = 6
        read_dex._aptos.view = AsyncMock(return_value=_view_bytes(["2500000"]))
        assert await read_dex.usdc_balance("0x" + "aa" * 32) == 2.5

    async def test_token_balance_scales_by_decimals(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.view = AsyncMock(return_value=_view_bytes(["1000"]))
        result = await read_dex.token_balance("0x" + "aa" * 32, "0x" + "bb" * 32, 3)
        assert result == 1.0

    async def test_account_balance(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.view = AsyncMock(return_value=_view_bytes(["123456"]))
        assert await read_dex.account_balance("0x" + "aa" * 32) == 123456
        pkg = read_dex._config.deployment.package
        assert (
            read_dex._aptos.view.call_args.args[0]
            == f"{pkg}::perp_engine::get_cross_total_collateral_value"
        )

    async def test_position_size(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.view = AsyncMock(return_value=_view_bytes(["42"]))
        result = await read_dex.position_size("0x" + "aa" * 32, "0x" + "11" * 32)
        assert result == ["42"]


class TestGetCrossedPosition:
    async def test_returns_parsed_position(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.account_resource = AsyncMock(return_value={"positions": []})
        result = await read_dex.get_crossed_position("0x" + "aa" * 32)
        assert isinstance(result, CrossedPosition)
        assert result.positions == []

    async def test_returns_none_on_error(self, read_dex: DecibelReadDex) -> None:
        read_dex._aptos.account_resource = AsyncMock(side_effect=Exception("no resource"))
        assert await read_dex.get_crossed_position("0x" + "aa" * 32) is None


class TestConstructionAndLifecycle:
    def _build(self, config: DecibelConfig) -> DecibelReadDex:
        with (
            patch("decibel.read.RestClient"),
            patch("decibel.read.DecibelWsSubscription"),
            patch("decibel.read.httpx.AsyncClient"),
        ):
            return DecibelReadDex(config, api_key="k")

    def test_constructor_wires_all_readers(self, test_config: DecibelConfig) -> None:
        dex = self._build(test_config)
        for attr in _READER_ATTRS:
            assert hasattr(dex, attr), attr
        assert dex._config is test_config
        assert dex._usdc_decimals_cache is None

    async def test_close_closes_ws_and_http(self, test_config: DecibelConfig) -> None:
        dex = self._build(test_config)
        dex.ws.close = AsyncMock()
        dex._http_client.aclose = AsyncMock()
        await dex.close()
        dex.ws.close.assert_awaited_once()
        dex._http_client.aclose.assert_awaited_once()

    async def test_async_context_manager(self, test_config: DecibelConfig) -> None:
        dex = self._build(test_config)
        dex.ws.close = AsyncMock()
        dex._http_client.aclose = AsyncMock()
        async with dex as ctx:
            assert ctx is dex
        dex.ws.close.assert_awaited_once()
        dex._http_client.aclose.assert_awaited_once()
