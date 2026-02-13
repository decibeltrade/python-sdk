from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Annotated, Any, Literal

from aptos_sdk.account_address import AccountAddress
from pydantic import BaseModel, ConfigDict, Field, RootModel

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
]


class MarketMode(StrEnum):
    OPEN = "Open"
    REDUCE_ONLY = "ReduceOnly"
    ALLOWLIST_ONLY = "AllowlistOnly"
    HALT = "Halt"
    DELISTING = "Delisting"


class PerpMarket(BaseModel):
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
    async def get_all(self) -> list[PerpMarket]:
        response, _, _ = await self.get_request(
            model=_PerpMarketList,
            url=f"{self.config.trading_http_url}/api/v1/markets",
        )
        # TODO: Remove once API is fixed and doesn't return duplicate markets
        seen: set[str] = set()
        unique: list[PerpMarket] = []
        for market in response.root:
            if market.market_addr not in seen:
                seen.add(market.market_addr)
                unique.append(market)
        return unique

    async def get_by_name(self, market_name: str) -> PerpMarketConfig | None:
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
        result_bytes = await self.aptos.view(
            f"{self.config.deployment.package}::perp_engine::list_markets",
            [],
            [],
        )
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return [str(addr) for addr in result[0]]

    async def market_name_by_address(self, market_addr: str) -> str:
        result_bytes = await self.aptos.view(
            f"{self.config.deployment.package}::perp_engine::market_name",
            [],
            [market_addr],
        )
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return str(result[0])
