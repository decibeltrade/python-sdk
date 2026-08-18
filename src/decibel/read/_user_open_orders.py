from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from .._asset_type import AssetTypeName, to_asset_type_param
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .._asset_type import AssetTypeFilter
    from ._ws import Unsubscribe

__all__ = [
    "UserOpenOrder",
    "UserOpenOrdersReader",
    "UserOpenOrdersResponse",
    "UserOpenOrdersWsMessage",
]


class UserOpenOrder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Absent on API versions that predate spot support (treat as "perp").
    asset_type: AssetTypeName | None = None
    # Spot orders carry the explicit time-in-force ("GTC"/"IOC"/"POST_ONLY").
    time_in_force: str | None = None
    parent: str
    market: str
    order_id: str
    client_order_id: str | None
    orig_size: float | None
    remaining_size: float | None
    size_delta: float | None
    price: float | None
    is_buy: bool
    details: str
    transaction_version: int
    unix_ms: int
    is_tpsl: bool
    tp_order_id: str | None = None
    tp_trigger_price: float | None
    tp_limit_price: float | None
    sl_order_id: str | None = None
    sl_trigger_price: float | None
    sl_limit_price: float | None
    order_type: str | None = None
    trigger_condition: str | None = None
    order_direction: str | None = None
    is_reduce_only: bool | None = None


class UserOpenOrdersResponse(BaseModel):
    items: list[UserOpenOrder]
    total_count: int


class UserOpenOrdersWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    orders: list[UserOpenOrder]


class UserOpenOrdersReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        limit: int | None = None,
        offset: int | None = None,
        asset_type: AssetTypeFilter = "perp",
    ) -> UserOpenOrdersResponse:
        """Get the open orders for a subaccount.

        ``asset_type`` is a server-side product filter (default ``"perp"``). Pass ``"spot"`` to
        scope the response (and its pagination) to spot, or ``"all"`` to omit the param and
        receive perp and spot merged — each row then carries ``asset_type`` for client-side demux.
        """
        params: dict[str, str] = {"account": sub_addr}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        asset_type_param = to_asset_type_param(asset_type)
        if asset_type_param is not None:
            params["asset_type"] = asset_type_param

        response, _, _ = await self.get_request(
            model=UserOpenOrdersResponse,
            url=f"{self.config.trading_http_url}/api/v1/open_orders",
            params=params,
        )
        return response

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserOpenOrdersWsMessage], None]
            | Callable[[UserOpenOrdersWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"account_open_orders:{sub_addr}"
        return self.ws.subscribe(topic, UserOpenOrdersWsMessage, on_data)
