from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "AccountOverview",
    "AccountOverviewReader",
    "AccountOverviewWsMessage",
    "VolumeWindow",
]


class VolumeWindow(StrEnum):
    SEVEN_DAYS = "7d"
    FOURTEEN_DAYS = "14d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"


class AccountOverview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    perp_equity_balance: float
    unrealized_pnl: float
    unrealized_funding_cost: float
    cross_margin_ratio: float
    maintenance_margin: float
    cross_account_leverage_ratio: float | None
    volume: float | None
    net_deposits: float | None = None
    all_time_return: float | None
    pnl_90d: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    weekly_win_rate_12w: float | None
    average_cash_position: float | None
    average_leverage: float | None
    cross_account_position: float
    total_margin: float
    usdc_cross_withdrawable_balance: float
    usdc_isolated_withdrawable_balance: float
    realized_pnl: float | None
    liquidation_fees_paid: float | None
    liquidation_losses: float | None


class _AccountOverviewWs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    perp_equity_balance: float
    unrealized_pnl: float
    unrealized_funding_cost: float
    cross_margin_ratio: float
    maintenance_margin: float
    cross_account_leverage_ratio: float | None
    net_deposits: float | None = None
    all_time_return: float | None
    pnl_90d: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    weekly_win_rate_12w: float | None
    average_cash_position: float | None
    average_leverage: float | None
    cross_account_position: float
    total_margin: float
    usdc_cross_withdrawable_balance: float
    usdc_isolated_withdrawable_balance: float
    realized_pnl: float | None
    liquidation_fees_paid: float | None
    liquidation_losses: float | None


class AccountOverviewWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_overview: _AccountOverviewWs


class AccountOverviewReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        volume_window: VolumeWindow | None = None,
        include_performance: bool = False,
    ) -> AccountOverview:
        params: dict[str, str] = {"account": sub_addr}
        if volume_window is not None:
            params["volume_window"] = volume_window.value
        if include_performance:
            params["include_performance"] = "true"

        response, _, _ = await self.get_request(
            model=AccountOverview,
            url=f"{self.config.trading_http_url}/api/v1/account_overviews",
            params=params,
        )
        return response

    def subscribe_by_addr(
        self,
        sub_addr: str,
        on_data: (
            Callable[[AccountOverviewWsMessage], None]
            | Callable[[AccountOverviewWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        topic = f"account_overview:{sub_addr}"
        return self.ws.subscribe(topic, AccountOverviewWsMessage, on_data)
