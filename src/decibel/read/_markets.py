from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Annotated, Any, Literal

from aptos_sdk.account_address import AccountAddress
from pydantic import BaseModel, ConfigDict, Field, RootModel

from .._asset_type import AssetTypeName, is_spot
from .._utils import get_market_addr
from ._base import BaseReader

logger = logging.getLogger(__name__)

__all__ = [
    "MarketMode",
    "MarketModeConfig",
    "MarketsReader",
    "PerpMarket",
    "PerpMarketConfig",
    "SzPrecision",
    "is_perp_market",
    "is_spot_market",
]


class MarketMode(StrEnum):
    OPEN = "Open"
    REDUCE_ONLY = "ReduceOnly"
    ALLOWLIST_ONLY = "AllowlistOnly"
    HALT = "Halt"
    DELISTING = "Delisting"


class PerpMarket(BaseModel):
    """A ``/markets`` row of either product.

    ``/api/v1/markets`` mixes perp and spot rows in one list, discriminated by ``asset_type``.
    Spot rows reuse this shape with different field semantics: ``sz_decimals`` is the base
    asset's decimals, ``px_decimals`` the quote asset's, and the perp-only fields
    (``max_leverage``, ``max_open_interest``) are zeroed. Use :func:`is_spot_market` /
    :func:`is_perp_market` (or ``asset_type`` directly) to demux.
    """

    model_config = ConfigDict(populate_by_name=True)

    market_addr: str
    market_name: str
    sz_decimals: int
    px_decimals: int
    max_leverage: float
    tick_size: float
    min_size: float
    lot_size: float
    max_open_interest: float
    mode: MarketMode
    # Absent on API versions that predate spot support (treat as "perp").
    asset_type: AssetTypeName | None = None


def is_spot_market(market: PerpMarket) -> bool:
    return is_spot(market.asset_type)


def is_perp_market(market: PerpMarket) -> bool:
    """Rows without ``asset_type`` (pre-spot API versions) are perp."""
    return not is_spot(market.asset_type)


class MarketModeConfigOpen(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    variant: Literal["Open"] = Field(alias="__variant__")


class MarketModeConfigReduceOnly(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    variant: Literal["ReduceOnly"] = Field(alias="__variant__")


class MarketModeConfigAllowlistOnly(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    variant: Literal["AllowlistOnly"] = Field(alias="__variant__")
    allowlist: list[str]


class MarketModeConfigHalt(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    variant: Literal["Halt"] = Field(alias="__variant__")


MarketModeConfig = Annotated[
    MarketModeConfigOpen
    | MarketModeConfigReduceOnly
    | MarketModeConfigAllowlistOnly
    | MarketModeConfigHalt,
    Field(discriminator="variant"),
]


class SzPrecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    decimals: int
    multiplier: str


class PerpMarketConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    variant: Literal["V1"] = Field(alias="__variant__")
    name: str
    sz_precision: SzPrecision
    min_size: str
    lot_size: str
    ticker_size: str
    max_leverage: float
    mode: MarketModeConfig


class _PerpMarketList(RootModel[list[PerpMarket]]):
    pass


class MarketsReader(BaseReader):
    async def get_all(self, *, include_spot: bool = False) -> list[PerpMarket]:
        """Get all available markets.

        Spot rows are filtered out by default so existing perp consumers don't see spot
        markets masquerading as 0-leverage perps; pass ``include_spot=True`` to get the full
        list and demux with :func:`is_spot_market` / :func:`is_perp_market`.
        """
        response, _, _ = await self.get_request(
            model=_PerpMarketList,
            url=f"{self.config.trading_http_url}/api/v1/markets",
        )
        # TODO: Remove once API is fixed and doesn't return duplicate markets
        seen: set[str] = set()
        unique: list[PerpMarket] = []
        for market in response.root:
            if not include_spot and is_spot_market(market):
                continue
            if market.market_addr not in seen:
                seen.add(market.market_addr)
                unique.append(market)
        return unique

    async def get_all_spot(self) -> list[PerpMarket]:
        """Get all available spot markets. Client-side filter of ``/markets``."""
        markets = await self.get_all(include_spot=True)
        return [market for market in markets if is_spot_market(market)]

    async def get_by_name(self, market_name: str) -> PerpMarketConfig | None:
        """On-chain ``PerpMarketConfig`` for a **perp** market name.

        Perp-only, unlike the rest of this reader: the address is derived from
        ``perp_engine_global`` and the resource read is ``perp_market_config::PerpMarketConfig``,
        neither of which exists for spot. Passing a spot market name therefore returns ``None``
        rather than raising — as does a name that simply isn't listed. Use
        :meth:`get_all_spot` for spot market metadata.
        """
        # TODO: Handle different __variant__ values
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        try:
            resource = await self.aptos.account_resource(
                AccountAddress.from_str(market_addr),
                f"{self.config.deployment.package}::perp_market_config::PerpMarketConfig",
            )
            return PerpMarketConfig.model_validate(resource)
        except Exception as e:
            logger.error("Failed to get market config for %s: %s", market_name, e)
            return None

    async def list_market_addresses(self) -> list[str]:
        """Addresses of all registered **perp** markets (``perp_engine::list_markets``)."""
        result_bytes = await self.aptos.view(
            f"{self.config.deployment.package}::perp_engine::list_markets",
            [],
            [],
        )
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return [str(addr) for addr in result[0]]

    async def market_name_by_address(self, market_addr: str) -> str:
        """Name of a **perp** market (``perp_engine::market_name``); raises for a spot address."""
        result_bytes = await self.aptos.view(
            f"{self.config.deployment.package}::perp_engine::market_name",
            [],
            [market_addr],
        )
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return str(result[0])
