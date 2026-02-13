from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from aptos_sdk.account import Account

__all__ = [
    "TimeInForce",
    "PlaceOrderArgs",
    "PlaceTwapOrderArgs",
    "CancelOrderArgs",
    "CancelClientOrderArgs",
    "CancelTwapOrderArgs",
    "ConfigureUserSettingsArgs",
    "DelegateTradingArgs",
    "RevokeDelegationArgs",
    "PlaceTpSlOrderArgs",
    "UpdateTpOrderArgs",
    "UpdateSlOrderArgs",
    "CancelTpSlOrderArgs",
    "ApproveBuilderFeeArgs",
    "RevokeBuilderFeeArgs",
    "DeactivateSubaccountArgs",
    "DelegateDexActionsArgs",
    "PlaceBulkOrdersArgs",
    "CancelBulkOrderArgs",
]


class TimeInForce(IntEnum):
    GoodTillCanceled = 0
    PostOnly = 1
    ImmediateOrCancel = 2


class PlaceOrderArgs(TypedDict, total=False):
    market_name: str
    price: float
    size: float
    is_buy: bool
    time_in_force: TimeInForce
    is_reduce_only: bool
    client_order_id: str | None
    stop_price: float | None
    tp_trigger_price: float | None
    tp_limit_price: float | None
    sl_trigger_price: float | None
    sl_limit_price: float | None
    builder_addr: str | None
    builder_fee: float | None
    subaccount_addr: str | None
    account_override: Account | None
    tick_size: float | None


class PlaceTwapOrderArgs(TypedDict, total=False):
    market_name: str
    size: float
    is_buy: bool
    is_reduce_only: bool
    client_order_id: str | None
    twap_frequency_seconds: int
    twap_duration_seconds: int
    builder_address: str | None
    builder_fees: float | None
    subaccount_addr: str | None
    account_override: Account | None


class CancelOrderArgs(TypedDict, total=False):
    order_id: int | str
    market_name: NotRequired[str]
    market_addr: NotRequired[str]
    subaccount_addr: str | None
    account_override: Account | None


class CancelClientOrderArgs(TypedDict):
    client_order_id: str
    market_name: str
    subaccount_addr: NotRequired[str | None]
    account_override: NotRequired[Account | None]


class CancelTwapOrderArgs(TypedDict):
    order_id: str
    market_addr: str
    subaccount_addr: NotRequired[str | None]
    account_override: NotRequired[Account | None]


class ConfigureUserSettingsArgs(TypedDict):
    market_addr: str
    subaccount_addr: str
    is_cross: bool
    user_leverage: int


class DelegateTradingArgs(TypedDict):
    subaccount_addr: str
    account_to_delegate_to: str
    expiration_timestamp_secs: NotRequired[int | None]


class RevokeDelegationArgs(TypedDict):
    account_to_revoke: str
    subaccount_addr: NotRequired[str | None]


class PlaceTpSlOrderArgs(TypedDict, total=False):
    market_addr: str
    tp_trigger_price: float | None
    tp_limit_price: float | None
    tp_size: float | None
    sl_trigger_price: float | None
    sl_limit_price: float | None
    sl_size: float | None
    subaccount_addr: str | None
    account_override: Account | None
    tick_size: float | None


class UpdateTpOrderArgs(TypedDict, total=False):
    market_addr: str
    prev_order_id: int | str
    tp_trigger_price: float | None
    tp_limit_price: float | None
    tp_size: float | None
    subaccount_addr: str | None
    account_override: Account | None


class UpdateSlOrderArgs(TypedDict, total=False):
    market_addr: str
    prev_order_id: int | str
    sl_trigger_price: float | None
    sl_limit_price: float | None
    sl_size: float | None
    subaccount_addr: str | None
    account_override: Account | None


class CancelTpSlOrderArgs(TypedDict):
    market_addr: str
    order_id: int | str
    subaccount_addr: NotRequired[str | None]
    account_override: NotRequired[Account | None]


class ApproveBuilderFeeArgs(TypedDict):
    builder_addr: str
    max_fee: int
    subaccount_addr: NotRequired[str | None]


class RevokeBuilderFeeArgs(TypedDict):
    builder_addr: str
    subaccount_addr: NotRequired[str | None]


class DeactivateSubaccountArgs(TypedDict):
    subaccount_addr: str
    revoke_all_delegations: NotRequired[bool]


class DelegateDexActionsArgs(TypedDict):
    vault_address: str
    account_to_delegate_to: str
    expiration_timestamp_secs: NotRequired[int | None]


class PlaceBulkOrdersArgs(TypedDict, total=False):
    market_name: str
    sequence_number: int
    bid_prices: list[int]
    bid_sizes: list[int]
    ask_prices: list[int]
    ask_sizes: list[int]
    builder_addr: str | None
    builder_fee: int | None
    subaccount_addr: str | None
    account_override: Account | None


class CancelBulkOrderArgs(TypedDict, total=False):
    market_name: str
    subaccount_addr: str | None
    account_override: Account | None
