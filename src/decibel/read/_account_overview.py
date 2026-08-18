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
    "SecondaryCollateral",
    "SpotInFlightOrder",
    "SpotMetrics",
    "SpotOverview",
    "SpotPosition",
    "VolumeWindow",
]


class VolumeWindow(StrEnum):
    SEVEN_DAYS = "7d"
    FOURTEEN_DAYS = "14d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"


class SecondaryCollateral(BaseModel):
    """Secondary (non-USDC) collateral held in cross margin."""

    model_config = ConfigDict(populate_by_name=True)

    #: On-chain asset type address (e.g. the DLP fungible asset address).
    asset_type: str
    #: Raw balance normalized to human units (``balance / 10**decimals``).
    amount: float
    #: USDC-equivalent value after applying the haircut.
    value_in_usdc: float
    #: NAV per unit in USDC terms (oracle price / ``10**collateral_decimals``).
    nav_per_unit: float
    #: Haircut applied to the oracle price for margin purposes, in basis points.
    haircut_bps: float
    #: Max amount of this asset withdrawable without violating margin requirements.
    withdrawable_amount: float


class SpotPosition(BaseModel):
    """A non-USDC asset held in the subaccount's spot inventory (typically APT)."""

    model_config = ConfigDict(populate_by_name=True)

    #: FA metadata address for the held asset.
    asset_addr: str
    #: Symbol from the spot market (e.g. ``"APT"``); empty when the asset is no market's base.
    asset_symbol: str
    #: Balance normalized to human units (``raw_balance / 10**decimals``).
    amount: float
    #: ``amount`` x current mark price (mid-of-orderbook, last trade as fallback).
    usd_value: float
    #: Weighted-average cost basis for the currently-held amount, in USD. 0 when the asset was
    #: acquired without an on-book spot trade (e.g. an FA transfer in).
    entry_notional_usd: float
    #: ``usd_value - entry_notional_usd``. Negative when mark is below average cost.
    unrealized_pnl_usd: float


class SpotInFlightOrder(BaseModel):
    """An open spot order and the funds it reserves (USDC for bids, base asset for asks)."""

    model_config = ConfigDict(populate_by_name=True)

    market_addr: str
    order_id: str
    is_bid: bool
    #: FA metadata address for the reserved asset (quote for bids, base for asks).
    reserved_asset: str
    #: Reserved amount in human units.
    reserved_amount: float
    #: USDC-equivalent value at the current mark.
    reserved_usd_value: float


class SpotMetrics(BaseModel):
    """Aggregate spot trading metrics for the subaccount, summed across assets.

    Fees are taker-attributed; realized PnL uses lifetime weighted-average cost basis.
    """

    model_config = ConfigDict(populate_by_name=True)

    #: Cumulative spot volume traded (both taker and maker sides), USD.
    cumulative_volume_usd: float
    #: Cumulative fees paid on fills where this account was the taker, USD.
    cumulative_taker_fees_usd: float
    #: Cumulative fees paid on fills where this account was the maker, USD.
    cumulative_maker_fees_usd: float
    #: Cumulative realized PnL from spot sells, USD.
    cumulative_realized_pnl_usd: float


class SpotOverview(BaseModel):
    """Spot-tradable inventory for the subaccount.

    Covers assets held in the per-user fungible store, including USDC as a PnL-less position;
    ``in_flight_orders`` covers amounts locked in open spot orders.
    """

    model_config = ConfigDict(populate_by_name=True)

    positions: list[SpotPosition]
    #: USDC-equivalent value of every position + reserved amounts in open spot orders.
    total_usd: float
    in_flight_orders: list[SpotInFlightOrder]
    #: Absent when the subaccount has never traded spot.
    metrics: SpotMetrics | None = None


class _AccountOverviewBase(BaseModel):
    """Fields shared by the REST and WS account-overview payloads.

    The WS payload is the REST payload minus ``volume``.
    """

    model_config = ConfigDict(populate_by_name=True)

    perp_equity_balance: float
    perp_equity_haircutted: float | None = None
    unrealized_pnl: float
    unrealized_funding_cost: float
    cross_margin_ratio: float
    maintenance_margin: float
    cross_account_leverage_ratio: float | None
    #: Net deposits (total deposits - total withdrawals) in USDC.
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
    #: Cross-margin deficit: 0 when healthy, negative when the account has a margin hole. When
    #: negative, new deposits partially fill the deficit before becoming available to trade.
    margin_deficit: float | None = None
    realized_pnl: float | None
    liquidation_fees_paid: float | None
    liquidation_losses: float | None
    #: Non-trade fee income (vault/BLP accounts only) — protocol fee distributions that are not
    #: captured in ``realized_pnl``.
    fee_income: float | None = None
    #: Total USDC value of vault shares attributed to this subaccount (free + pledged-as-
    #: collateral). For display only — do NOT sum with ``perp_equity_balance``, since the
    #: pledged portion is already counted there via ``secondary_collateral``. Use
    #: ``free_vault_equity`` for total-wealth calculations. ``None`` when not yet available.
    vault_equity: float | None = None
    #: USDC value of vault shares NOT currently pledged as DLP collateral on this subaccount's
    #: perp account ("free" shares x NAV). Additive complement to ``perp_equity_balance``:
    #: their sum is total subaccount wealth with no double-count of pledged DLP. 0 for users
    #: who pledge all their shares as collateral. ``None`` when not yet available.
    free_vault_equity: float | None = None
    #: Secondary (non-USDC) collateral held in cross margin. ``None`` when none exists or
    #: oracle data is unavailable.
    secondary_collateral: list[SecondaryCollateral] | None = None
    #: Total cross-margin buying power across all collateral assets (USDC + secondary):
    #: ``max(0, raw_free_collateral - order_margin)``. Use for "Available to Trade" display.
    cross_available_to_trade: float | None = None
    #: Spot inventory + open-order reservations + trading metrics for this subaccount.
    #: ``None`` for wallet-only owners or when spot enrichment fails.
    spot: SpotOverview | None = None


class AccountOverview(_AccountOverviewBase):
    volume: float | None


class _AccountOverviewWs(_AccountOverviewBase):
    pass


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
