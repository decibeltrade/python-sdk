from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "UserPosition",
    "UserPositionsReader",
    "UserPositionsWsMessage",
]


class UserPosition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    user: str
    size: float
    user_leverage: float
    entry_price: float
    is_isolated: bool
    unrealized_funding: float
    estimated_liquidation_price: float
    tp_order_id: str | None
    tp_trigger_price: float | None
    tp_limit_price: float | None
    sl_order_id: str | None
    sl_trigger_price: float | None
    sl_limit_price: float | None
    has_fixed_sized_tpsls: bool


class _UserPositionsList(RootModel[list[UserPosition]]):
    pass


class UserPositionsWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    positions: list[UserPosition]


class UserPositionsReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        market_addr: str | None = None,
        include_deleted: bool = False,
        limit: int = 10,
    ) -> list[UserPosition]:
        params: dict[str, str] = {
            "account": sub_addr,
            "include_deleted": str(include_deleted).lower(),
            "limit": str(limit),
        }
        if market_addr is not None:
            params["market_address"] = market_addr

        response, _, _ = await self.get_request(
            model=_UserPositionsList,
            url=f"{self.config.trading_http_url}/api/v1/account_positions",
            params=params,
        )
        return response.root

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserPositionsWsMessage], None]
            | Callable[[UserPositionsWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"account_positions:{sub_addr}"
        return self.ws.subscribe(topic, UserPositionsWsMessage, on_data)
