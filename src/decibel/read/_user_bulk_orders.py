from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "UserBulkOrder",
    "UserBulkOrdersReader",
    "UserBulkOrderWsMessage",
]


class UserBulkOrder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    sequence_number: int
    previous_seq_num: int
    bid_prices: list[float]
    bid_sizes: list[float]
    ask_prices: list[float]
    ask_sizes: list[float]
    cancelled_bid_prices: list[float]
    cancelled_bid_sizes: list[float]
    cancelled_ask_prices: list[float]
    cancelled_ask_sizes: list[float]


class _UserBulkOrdersList(RootModel[list[UserBulkOrder]]):
    pass


class _UserBulkOrderInner(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    details: str
    bulk_order: UserBulkOrder


class UserBulkOrderWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    bulk_order: _UserBulkOrderInner


class UserBulkOrdersReader(BaseReader):
    async def get_by_addr(self, *, sub_addr: str, market: str | None = None) -> list[UserBulkOrder]:
        response, _, _ = await self.get_request(
            model=_UserBulkOrdersList,
            url=f"{self.config.trading_http_url}/api/v1/bulk_orders",
            params={"account": sub_addr, "market": market or "all"},
        )
        return response.root

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserBulkOrderWsMessage], None]
            | Callable[[UserBulkOrderWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"bulk_orders:{sub_addr}"
        return self.ws.subscribe(topic, UserBulkOrderWsMessage, on_data)
