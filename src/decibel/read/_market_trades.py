from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from .._utils import get_market_addr
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "MarketTrade",
    "MarketTradesReader",
    "MarketTradesResponse",
    "MarketTradeWsMessage",
]


class MarketTrade(BaseModel):
    """REST trade model — fields match the /api/v1/trades response."""

    model_config = ConfigDict(populate_by_name=True)

    account: str
    market: str
    action: str
    trade_id: str | int
    size: float
    price: float
    is_profit: bool
    realized_pnl_amount: float
    realized_funding_amount: float
    is_rebate: bool
    fee_amount: float
    order_id: str
    client_order_id: str
    source: str
    transaction_unix_ms: int
    transaction_version: int


class _WsTradeItem(BaseModel):
    """WS trade model — includes is_funding_positive, lacks source."""

    model_config = ConfigDict(populate_by_name=True)

    account: str
    market: str
    action: str
    trade_id: int
    size: float
    price: float
    is_profit: bool
    realized_pnl_amount: float
    is_funding_positive: bool
    realized_funding_amount: float
    is_rebate: bool
    fee_amount: float
    order_id: str
    client_order_id: str
    transaction_unix_ms: int
    transaction_version: int


class MarketTradesResponse(BaseModel):
    items: list[MarketTrade]
    total_count: int


class MarketTradeWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trades: list[_WsTradeItem]


class MarketTradesReader(BaseReader):
    async def get_by_name(
        self,
        market_name: str,
        *,
        limit: int | None = None,
    ) -> list[MarketTrade]:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        params: dict[str, str] = {"market": market_addr}
        if limit is not None:
            params["limit"] = str(limit)

        response, _, _ = await self.get_request(
            model=MarketTradesResponse,
            url=f"{self.config.trading_http_url}/api/v1/trades",
            params=params,
        )
        return response.items

    def subscribe_by_name(
        self,
        market_name: str,
        on_data: (
            Callable[[MarketTradeWsMessage], None]
            | Callable[[MarketTradeWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        topic = f"trades:{market_addr}"
        return self.ws.subscribe(topic, MarketTradeWsMessage, on_data)
