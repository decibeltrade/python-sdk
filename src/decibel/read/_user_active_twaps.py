from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "TwapStatus",
    "UserActiveTwap",
    "UserActiveTwapsReader",
    "UserActiveTwapsWsMessage",
]

TwapStatus = Literal["Finished", "Activated", "Cancelled"]


class UserActiveTwap(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    is_buy: bool
    order_id: str
    client_order_id: str
    is_reduce_only: bool
    start_unix_ms: int
    frequency_s: int
    duration_s: int
    orig_size: float
    remaining_size: float
    status: TwapStatus
    transaction_unix_ms: int
    transaction_version: int


class _UserActiveTwapsList(RootModel[list[UserActiveTwap]]):
    pass


class UserActiveTwapsWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    twaps: list[UserActiveTwap]


class UserActiveTwapsReader(BaseReader):
    async def get_by_addr(self, *, sub_addr: str) -> list[UserActiveTwap]:
        response, _, _ = await self.get_request(
            model=_UserActiveTwapsList,
            url=f"{self.config.trading_http_url}/api/v1/active_twaps",
            params={"account": sub_addr},
        )
        return response.root

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserActiveTwapsWsMessage], None]
            | Callable[[UserActiveTwapsWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"user_active_twaps:{sub_addr}"
        return self.ws.subscribe(topic, UserActiveTwapsWsMessage, on_data)
