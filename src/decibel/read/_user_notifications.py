from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader
from ._user_active_twaps import UserActiveTwap
from ._user_order_history import UserOrder

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "NotificationMetadata",
    "NotificationType",
    "UserNotificationWsMessage",
    "UserNotificationsReader",
]


class NotificationType(StrEnum):
    MarketOrderPlaced = "MarketOrderPlaced"
    LimitOrderPlaced = "LimitOrderPlaced"
    StopMarketOrderPlaced = "StopMarketOrderPlaced"
    StopMarketOrderTriggered = "StopMarketOrderTriggered"
    StopLimitOrderPlaced = "StopLimitOrderPlaced"
    StopLimitOrderTriggered = "StopLimitOrderTriggered"
    OrderPartiallyFilled = "OrderPartiallyFilled"
    OrderFilled = "OrderFilled"
    OrderSizeReduced = "OrderSizeReduced"
    OrderCancelled = "OrderCancelled"
    OrderRejected = "OrderRejected"
    OrderErrored = "OrderErrored"
    TwapOrderPlaced = "TwapOrderPlaced"
    TwapOrderTriggered = "TwapOrderTriggered"
    TwapOrderCompleted = "TwapOrderCompleted"
    TwapOrderCancelled = "TwapOrderCancelled"
    TwapOrderErrored = "TwapOrderErrored"
    AccountDeposit = "AccountDeposit"
    AccountWithdrawal = "AccountWithdrawal"
    TpSlSet = "TpSlSet"
    TpHit = "TpHit"
    SlHit = "SlHit"
    TpCancelled = "TpCancelled"
    SlCancelled = "SlCancelled"


class NotificationMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trigger_price: float | None = None
    reason: str | None = None
    amount: float | None = None
    filled_size: float | None = None


class _NotificationInner(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    notification_metadata: NotificationMetadata | None = None
    notification_type: NotificationType
    order: UserOrder | None = None
    twap: UserActiveTwap | None = None


class UserNotificationWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    notification: _NotificationInner


class UserNotificationsReader(BaseReader):
    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[UserNotificationWsMessage], None]
            | Callable[[UserNotificationWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"notifications:{sub_addr}"
        return self.ws.subscribe(topic, UserNotificationWsMessage, on_data)
