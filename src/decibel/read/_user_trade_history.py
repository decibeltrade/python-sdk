from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "UserTrade",
    "UserTradeAction",
    "UserTradeHistoryReader",
    "UserTradesResponse",
    "UserTradesWsMessage",
]

UserTradeAction = Literal["OpenLong", "CloseLong", "OpenShort", "CloseShort", "Net"]


class UserTrade(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    market: str
    action: UserTradeAction
    size: float
    price: float
    is_profit: bool
    realized_pnl_amount: float
    is_funding_positive: bool
    realized_funding_amount: float
    is_rebate: bool
    fee_amount: float
    transaction_unix_ms: int
    transaction_version: int


class UserTradesResponse(BaseModel):
    items: list[UserTrade]
    total_count: int


class UserTradesWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trades: list[UserTrade]


class UserTradeHistoryReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        limit: int = 10,
        offset: int = 0,
    ) -> UserTradesResponse:
        response, _, _ = await self.get_request(
            model=UserTradesResponse,
            url=f"{self.config.trading_http_url}/api/v1/trade_history",
            params={"account": sub_addr, "limit": str(limit), "offset": str(offset)},
        )
        return response

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserTradesWsMessage], None] | Callable[[UserTradesWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"user_trades:{sub_addr}"
        return self.ws.subscribe(topic, UserTradesWsMessage, on_data)
