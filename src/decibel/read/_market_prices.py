from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, RootModel

from .._utils import get_market_addr
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "MarketPrice",
    "MarketPriceWsMessage",
    "AllMarketPricesWsMessage",
    "MarketPricesReader",
]


class MarketPrice(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    mark_px: float
    mid_px: float
    oracle_px: float
    funding_rate_bps: float
    is_funding_positive: bool
    open_interest: float
    transaction_unix_ms: int


class _MarketPriceList(RootModel[list[MarketPrice]]):
    pass


class MarketPriceWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    price: MarketPrice


class AllMarketPricesWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prices: list[MarketPrice]


class MarketPricesReader(BaseReader):
    async def get_all(self) -> list[MarketPrice]:
        response, _, _ = await self.get_request(
            model=_MarketPriceList,
            url=f"{self.config.trading_http_url}/api/v1/prices",
        )
        return response.root

    async def get_by_name(self, market_name: str) -> list[MarketPrice]:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        response, _, _ = await self.get_request(
            model=_MarketPriceList,
            url=f"{self.config.trading_http_url}/api/v1/prices",
            params={"market": market_addr},
        )
        return response.root

    def subscribe_by_name(
        self,
        market_name: str,
        on_data: (
            Callable[[MarketPriceWsMessage], None]
            | Callable[[MarketPriceWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        topic = f"market_price:{market_addr}"
        return self.ws.subscribe(topic, MarketPriceWsMessage, on_data)

    def subscribe_by_address(
        self,
        market_addr: str,
        on_data: (
            Callable[[MarketPriceWsMessage], None]
            | Callable[[MarketPriceWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"market_price:{market_addr}"
        return self.ws.subscribe(topic, MarketPriceWsMessage, on_data)

    def subscribe_all(
        self,
        on_data: (
            Callable[[AllMarketPricesWsMessage], None]
            | Callable[[AllMarketPricesWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = "all_market_prices"
        return self.ws.subscribe(topic, AllMarketPricesWsMessage, on_data)
