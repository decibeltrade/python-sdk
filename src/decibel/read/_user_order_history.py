from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "UserOrder",
    "UserOrders",
    "UserOrderHistoryReader",
    "UserOrdersWsMessage",
]


class UserOrder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    parent: str
    market: str
    client_order_id: str
    order_id: str
    status: str
    order_type: str
    trigger_condition: str
    order_direction: str
    orig_size: float | None
    remaining_size: float | None
    size_delta: float | None
    price: float | None
    is_buy: bool
    is_reduce_only: bool
    details: str
    is_tpsl: bool
    tp_order_id: str | None = None
    tp_trigger_price: float | None
    tp_limit_price: float | None
    sl_order_id: str | None = None
    sl_trigger_price: float | None
    sl_limit_price: float | None
    transaction_version: int
    unix_ms: int


class UserOrders(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[UserOrder]
    total_count: int


class _UserOrderInner(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    details: str
    order: UserOrder
    status: str


class UserOrdersWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    order: _UserOrderInner


class UserOrderHistoryReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> UserOrders:
        params: dict[str, str] = {"user": sub_addr}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        response, _, _ = await self.get_request(
            model=UserOrders,
            url=f"{self.config.trading_http_url}/api/v1/order_history",
            params=params,
        )
        return response

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserOrdersWsMessage], None] | Callable[[UserOrdersWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"order_updates:{sub_addr}"
        return self.ws.subscribe(topic, UserOrdersWsMessage, on_data)
