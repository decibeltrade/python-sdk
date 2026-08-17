from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from .._asset_type import AssetTypeName, to_asset_type_param
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .._asset_type import AssetTypeFilter
    from ._ws import Unsubscribe

__all__ = [
    "UserTrade",
    "UserTradeAction",
    "UserTradeHistoryReader",
    "UserTradesResponse",
    "UserTradesWsMessage",
]

# Perp trades are position-centric (OpenLong/CloseShort/...); spot trades carry the side from
# this row's perspective (Buy/Sell). Without the spot variants, the first spot fill on the
# `user_trades` WS topic fails validation and kills the subscription.
UserTradeAction = Literal["OpenLong", "CloseLong", "OpenShort", "CloseShort", "Net", "Buy", "Sell"]


class UserTrade(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Absent on API versions that predate spot support (treat as "perp").
    asset_type: AssetTypeName | None = None
    account: str
    market: str
    action: UserTradeAction
    size: float
    price: float
    is_profit: bool
    realized_pnl_amount: float
    is_funding_positive: bool | None = None
    realized_funding_amount: float
    is_rebate: bool
    fee_amount: float
    # FA metadata address of the asset `fee_amount` is denominated in. Spot only (base asset for
    # the buyer, quote for the seller); absent on perp rows, where the fee is implicitly the
    # collateral asset (USDC).
    fee_asset: str | None = None
    transaction_unix_ms: int
    transaction_version: int


class UserTradesResponse(BaseModel):
    items: list[UserTrade]
    total_count: int | None = None


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
        asset_type: AssetTypeFilter = "perp",
    ) -> UserTradesResponse:
        """Get the trade history for a subaccount.

        ``asset_type`` is a server-side product filter (default ``"perp"``). Pass ``"spot"`` to
        scope the response (and its pagination) to spot, or ``"all"`` to omit the param and
        receive perp and spot merged — each row then carries ``asset_type`` for client-side demux.
        """
        params: dict[str, str] = {
            "account": sub_addr,
            "limit": str(limit),
            "offset": str(offset),
        }
        asset_type_param = to_asset_type_param(asset_type)
        if asset_type_param is not None:
            params["asset_type"] = asset_type_param

        response, _, _ = await self.get_request(
            model=UserTradesResponse,
            url=f"{self.config.trading_http_url}/api/v1/trade_history",
            params=params,
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
