from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from .._asset_type import AssetTypeName
from .._utils import get_market_addr_for_product
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
    """REST trade model — fields match the /api/v1/trades response.

    Spot and perp trades share this shape. On spot, ``action`` is the side (``"Buy"`` /
    ``"Sell"``) rather than the perp position-centric values (``"OpenLong"``, ...), the
    perp-only PnL/funding fields are zero, and ``fee_asset`` names the fungible asset
    ``fee_amount`` is denominated in.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Absent on API versions that predate spot support (treat as "perp").
    asset_type: AssetTypeName | None = None
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
    # Spot only: FA address `fee_amount` is denominated in; absent on perp.
    fee_asset: str | None = None
    order_id: str
    client_order_id: str
    source: str
    transaction_unix_ms: int
    transaction_version: int


class _WsTradeItem(BaseModel):
    """WS trade model — includes is_funding_positive, lacks source."""

    model_config = ConfigDict(populate_by_name=True)

    asset_type: AssetTypeName | None = None
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
    fee_asset: str | None = None
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
        asset_type: AssetTypeName = AssetTypeName.PERP,
    ) -> list[MarketTrade]:
        """Get the latest trades for a market by name.

        Perp and spot derive different addresses for the same name, so pass
        ``asset_type=AssetTypeName.SPOT`` for spot markets — or prefer :meth:`get_by_addr`.
        """
        market_addr = get_market_addr_for_product(market_name, asset_type, self.config.deployment)
        return await self.get_by_addr(market_addr, limit=limit)

    async def get_by_addr(
        self,
        market_addr: str,
        *,
        limit: int | None = None,
    ) -> list[MarketTrade]:
        """Get the latest trades by market object address — product-agnostic."""
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
        asset_type: AssetTypeName = AssetTypeName.PERP,
    ) -> Unsubscribe:
        market_addr = get_market_addr_for_product(market_name, asset_type, self.config.deployment)
        return self.subscribe_by_addr(market_addr, on_data)

    def subscribe_by_addr(
        self,
        market_addr: str,
        on_data: (
            Callable[[MarketTradeWsMessage], None]
            | Callable[[MarketTradeWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        """Subscribe to trades by market object address — product-agnostic."""
        topic = f"trades:{market_addr}"
        return self.ws.subscribe(topic, MarketTradeWsMessage, on_data)
