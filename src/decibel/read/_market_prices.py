from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, RootModel

from .._asset_type import AssetTypeName
from .._utils import get_market_addr
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "AllMarketPricesWsMessage",
    "AllSpotMidsWsMessage",
    "MarketPrice",
    "MarketPricesReader",
    "MarketPriceWsMessage",
    "Mid",
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


class Mid(BaseModel):
    """Mid / last-trade price for one market.

    ``mid`` is ``None`` unless both book sides have resting liquidity; ``last_trade_price`` is
    ``None`` until the market's first fill.
    """

    model_config = ConfigDict(populate_by_name=True)

    market_addr: str
    asset_type: AssetTypeName
    mid: float | None
    last_trade_price: float | None
    transaction_unix_ms: int


class AllSpotMidsWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mids: list[Mid]


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

    def subscribe_all_spot_mids(
        self,
        on_data: (
            Callable[[AllSpotMidsWsMessage], None]
            | Callable[[AllSpotMidsWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        """Subscribe to mid/last-trade price updates for all spot markets.

        Each update carries one row per registered spot market.
        """
        topic = "all_spot_mids"
        return self.ws.subscribe(topic, AllSpotMidsWsMessage, on_data)
