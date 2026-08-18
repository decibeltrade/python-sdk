"""Tests for the spot/perp product split on the shared readers.

Covers the ``asset_type`` discriminator, per-product market-address derivation, and the
perp-by-default guarantee that keeps pre-spot consumers unchanged.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel._asset_type import AssetTypeName, is_spot, to_asset_type_param
from decibel._utils import get_market_addr, get_spot_market_addr
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
    return patch.object(reader, "get_request", new=AsyncMock(return_value=(response, 200, "OK")))


def _params_of(mock: Any) -> dict[str, str]:
    return mock.call_args.kwargs.get("params") or {}


class TestAssetTypeHelpers:
    def test_filter_maps_to_wire_param(self) -> None:
        assert to_asset_type_param("perp") == "perp"
        assert to_asset_type_param("spot") == "spot"

    def test_all_omits_the_param(self) -> None:
        assert to_asset_type_param("all") is None

    def test_is_spot(self) -> None:
        assert is_spot(AssetTypeName.SPOT) is True
        assert is_spot("spot") is True
        assert is_spot(AssetTypeName.PERP) is False
        # Absent or unknown means perp: pre-spot API versions omit the field entirely.
        assert is_spot(None) is False
        assert is_spot("something_new") is False

    def test_enum_values_are_wire_strings(self) -> None:
        assert AssetTypeName.PERP.value == "perp"
        assert AssetTypeName.SPOT.value == "spot"


class TestMarketDepthProductRouting:
    async def test_perp_is_the_default(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader(reader_deps)
        expected = get_market_addr("APT/USD", reader_deps.config.deployment.perp_engine_global)

        with patch.object(reader, "get_by_addr", new=AsyncMock()) as mock_addr:
            await reader.get_by_name("APT/USD")

        assert mock_addr.call_args.args[0] == expected

    async def test_spot_derives_from_the_package(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader(reader_deps)
        expected = get_spot_market_addr("APT/USDC", reader_deps.config.deployment.package)

        with patch.object(reader, "get_by_addr", new=AsyncMock()) as mock_addr:
            await reader.get_by_name("APT/USDC", asset_type=AssetTypeName.SPOT)

        assert mock_addr.call_args.args[0] == expected

    def test_subscribe_by_name_routes_per_product(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_depth import MarketDepthReader

        reader = MarketDepthReader(reader_deps)
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_name("APT/USDC", 1, MagicMock(), asset_type=AssetTypeName.SPOT)

        topic = reader_deps.ws.subscribe.call_args[0][0]
        assert get_spot_market_addr("APT/USDC", reader_deps.config.deployment.package) in topic


class TestUserOpenOrdersAssetTypeFilter:
    async def test_defaults_to_perp(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersResponse

        reader = UserOpenOrdersReader(reader_deps)

        with _patch_get(reader, UserOpenOrdersResponse(items=[], total_count=0)) as mock_req:
            await reader.get_by_addr(sub_addr="0xuser")

        assert _params_of(mock_req)["asset_type"] == "perp"

    async def test_spot_filter(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersResponse

        reader = UserOpenOrdersReader(reader_deps)

        with _patch_get(reader, UserOpenOrdersResponse(items=[], total_count=0)) as mock_req:
            await reader.get_by_addr(sub_addr="0xuser", asset_type="spot")

        assert _params_of(mock_req)["asset_type"] == "spot"

    async def test_all_omits_the_param(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersResponse

        reader = UserOpenOrdersReader(reader_deps)

        with _patch_get(reader, UserOpenOrdersResponse(items=[], total_count=0)) as mock_req:
            await reader.get_by_addr(sub_addr="0xuser", asset_type="all")

        assert "asset_type" not in _params_of(mock_req)

    async def test_account_is_the_query_param(self, reader_deps: ReaderDeps) -> None:
        # The REST spec and the TypeScript SDK both send `account`, not `user`.
        from decibel.read._user_open_orders import UserOpenOrdersReader, UserOpenOrdersResponse

        reader = UserOpenOrdersReader(reader_deps)

        with _patch_get(reader, UserOpenOrdersResponse(items=[], total_count=0)) as mock_req:
            await reader.get_by_addr(sub_addr="0xuser")

        params = _params_of(mock_req)
        assert params["account"] == "0xuser"
        assert "user" not in params


class TestMarketsReaderSpotFiltering:
    def _market(self, name: str, asset_type: str | None) -> dict[str, Any]:
        return {
            "market_addr": f"0x{name}",
            "market_name": name,
            "sz_decimals": 8,
            "px_decimals": 6,
            "tick_size": 100,
            "lot_size": 1000,
            "min_size": 100,
            "max_leverage": 20,
            "max_open_interest": 1000.0,
            "mode": "Open",
            **({"asset_type": asset_type} if asset_type is not None else {}),
        }

    def test_asset_type_is_optional_on_rows(self) -> None:
        from decibel.read._markets import PerpMarket

        market = PerpMarket.model_validate(self._market("APT/USD", None))
        assert market.asset_type is None

    def test_is_spot_market_helper(self) -> None:
        from decibel.read._markets import PerpMarket, is_perp_market, is_spot_market

        spot = PerpMarket.model_validate(self._market("APT/USDC", "spot"))
        perp = PerpMarket.model_validate(self._market("APT/USD", "perp"))
        legacy = PerpMarket.model_validate(self._market("APT/USD", None))

        assert is_spot_market(spot) is True
        assert is_perp_market(spot) is False
        assert is_perp_market(perp) is True
        # A row with no asset_type predates spot, so it is a perp market.
        assert is_perp_market(legacy) is True
        assert is_spot_market(legacy) is False


class TestAllSpotMids:
    def test_subscribe_topic(self, reader_deps: ReaderDeps) -> None:
        from decibel.read._market_prices import AllSpotMidsWsMessage, MarketPricesReader

        reader = MarketPricesReader(reader_deps)
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_all_spot_mids(MagicMock())

        args = reader_deps.ws.subscribe.call_args[0]
        assert args[0] == "all_spot_mids"
        assert args[1] is AllSpotMidsWsMessage

    def test_mid_row_nullables(self) -> None:
        from decibel.read._market_prices import Mid

        mid = Mid.model_validate(
            {
                "market_addr": "0xmarket",
                "asset_type": "spot",
                "mid": None,
                "last_trade_price": None,
                "transaction_unix_ms": 1,
            }
        )
        assert mid.mid is None
        assert mid.asset_type == AssetTypeName.SPOT
