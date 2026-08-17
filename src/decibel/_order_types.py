from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "OrderEventClientOrderId",
    "OrderEventStatus",
    "OrderEventTimeInForce",
    "OrderEventTriggerCondition",
    "OrderEventOrderId",
    "OrderEvent",
    "SpotOrderPendingCbsEvent",
    "TwapEvent",
    "PlaceOrderSuccess",
    "PlaceOrderFailure",
    "PlaceOrderResult",
    "PlaceSpotOrderSuccess",
    "PlaceSpotOrderFailure",
    "PlaceSpotOrderResult",
    "PlaceBulkOrdersSuccess",
    "PlaceBulkOrdersFailure",
    "PlaceBulkOrdersResult",
]


class OrderEventClientOrderId(BaseModel):
    vec: list[Any]


class OrderEventStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    variant: str = Field(alias="__variant__")


class OrderEventTimeInForce(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    variant: str = Field(alias="__variant__")


class OrderEventTriggerCondition(BaseModel):
    vec: list[Any]


class OrderEventOrderId(BaseModel):
    order_id: str


class OrderEvent(BaseModel):
    client_order_id: OrderEventClientOrderId
    details: str
    is_bid: bool
    is_taker: bool
    market: str
    metadata_bytes: str
    order_id: str
    orig_size: str
    parent: str
    price: str
    remaining_size: str
    size_delta: str
    status: OrderEventStatus
    time_in_force: OrderEventTimeInForce
    trigger_condition: OrderEventTriggerCondition
    user: str


class SpotOrderPendingCbsEvent(BaseModel):
    """Emitted when a spot order is queued behind a rate-limited CBS withdrawal.

    The transaction succeeded, but the order is not on the book yet.
    """

    order_id: str
    withdraw_request_id: str
    subaccount_addr: str
    market: str | dict[str, Any]
    price: str
    orig_size: str
    is_bid: bool
    metadata: str | dict[str, Any]
    pfs_balance: str
    created_at: str


class TwapEvent(BaseModel):
    account: str
    duration_s: str
    frequency_s: str
    is_buy: bool
    is_reduce_only: bool
    market: str
    order_id: OrderEventOrderId
    orig_size: str
    remain_size: str
    start_time_s: str
    status: OrderEventStatus


class PlaceOrderSuccess(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: Literal[True] = True
    order_id: str | None = Field(default=None, alias="orderId")
    transaction_hash: str = Field(alias="transactionHash")


class PlaceOrderFailure(BaseModel):
    success: Literal[False] = False
    error: str


PlaceOrderResult = PlaceOrderSuccess | PlaceOrderFailure


class PlaceSpotOrderSuccess(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: Literal[True] = True
    order_id: str | None = Field(default=None, alias="orderId")
    #: True when the order was queued behind a rate-limited CBS withdrawal
    #: (:class:`SpotOrderPendingCbsEvent`) instead of reaching the book in this transaction.
    #: Poll the order endpoints for the real acknowledgment.
    pending_cbs: bool = Field(default=False, alias="pendingCbs")
    transaction_hash: str = Field(alias="transactionHash")


class PlaceSpotOrderFailure(BaseModel):
    success: Literal[False] = False
    error: str


PlaceSpotOrderResult = PlaceSpotOrderSuccess | PlaceSpotOrderFailure


class PlaceBulkOrdersSuccess(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: Literal[True] = True
    transaction_hash: str = Field(alias="transactionHash")


class PlaceBulkOrdersFailure(BaseModel):
    success: Literal[False] = False
    error: str


PlaceBulkOrdersResult = PlaceBulkOrdersSuccess | PlaceBulkOrdersFailure
