from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from .._utils import get_market_addr
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "MarketOrder",
    "MarketDepth",
    "MarketDepthWsMessage",
    "MarketDepthAggregationSize",
    "MarketDepthReader",
]

MarketDepthAggregationSize = Literal[1, 2, 5, 10, 100, 1000]


class MarketOrder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    price: float
    size: float


class MarketDepth(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    bids: list[MarketOrder]
    asks: list[MarketOrder]
    unix_ms: int


MarketDepthWsMessage = MarketDepth


class MarketDepthReader(BaseReader):
    async def get_by_name(self, market_name: str, *, limit: int | None = None) -> MarketDepth:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        params: dict[str, str] = {"market": market_addr}
        if limit is not None:
            params["limit"] = str(limit)

        response, _, _ = await self.get_request(
            model=MarketDepth,
            url=f"{self.config.trading_http_url}/api/v1/depth",
            params=params,
        )
        return response

    def subscribe_by_name(
        self,
        market_name: str,
        aggregation_size: MarketDepthAggregationSize,
        on_data: Callable[[MarketDepth], None] | Callable[[MarketDepth], Awaitable[None]],
    ) -> Unsubscribe:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        topic = f"depth:{market_addr}:{aggregation_size}"
        return self.ws.subscribe(topic, MarketDepth, on_data)

    def reset_subscription_by_name(
        self,
        market_name: str,
        aggregation_size: MarketDepthAggregationSize = 1,
    ) -> None:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        topic = f"depth:{market_addr}:{aggregation_size}"
        self.ws.reset(topic)

    def get_aggregation_sizes(
        self,
    ) -> tuple[Literal[1], Literal[2], Literal[5], Literal[10], Literal[100], Literal[1000]]:
        return (1, 2, 5, 10, 100, 1000)
