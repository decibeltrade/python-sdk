from __future__ import annotations

from typing import TYPE_CHECKING

from aptos_sdk.async_client import RestClient

from ._account_overview import (
    AccountOverview,
    AccountOverviewReader,
    AccountOverviewWsMessage,
    VolumeWindow,
)
from ._base import ReaderDeps
from ._candlesticks import (
    Candlestick,
    CandlestickInterval,
    CandlesticksReader,
    CandlestickWsMessage,
)
from ._delegations import Delegation, DelegationsReader
from ._leaderboard import (
    LeaderboardItem,
    LeaderboardReader,
    LeaderboardResponse,
    LeaderboardSortKey,
)
from ._market_contexts import MarketContext, MarketContextsReader
from ._market_depth import (
    MarketDepth,
    MarketDepthAggregationSize,
    MarketDepthReader,
    MarketDepthWsMessage,
    MarketOrder,
)
from ._market_prices import (
    AllMarketPricesWsMessage,
    MarketPrice,
    MarketPricesReader,
    MarketPriceWsMessage,
)
from ._market_trades import (
    MarketTrade,
    MarketTradesReader,
    MarketTradesResponse,
    MarketTradeWsMessage,
)
from ._markets import (
    MarketMode,
    MarketModeConfig,
    MarketsReader,
    PerpMarket,
    PerpMarketConfig,
    SzPrecision,
)
from ._portfolio_chart import (
    PortfolioChartItem,
    PortfolioChartReader,
    PortfolioChartTimeRange,
    PortfolioChartType,
)
from ._trading_points import (
    OwnerTradingPoints,
    SubaccountPoints,
    TradingPointsReader,
)
from ._types import (
    ActivateVaultArgs,
    AssetType,
    BalanceTable,
    CollateralBalanceSheet,
    CreateVaultArgs,
    CrossedPosition,
    DepositToVaultArgs,
    GlobalAccountsState,
    GlobalAccountsStateV1,
    LiquidationConfigV1,
    PerpPosition,
    Precision,
    Store,
    StoreExtendRef,
    WithdrawFromVaultArgs,
)
from ._user_active_twaps import (
    TwapStatus,
    UserActiveTwap,
    UserActiveTwapsReader,
    UserActiveTwapsWsMessage,
)
from ._user_bulk_orders import (
    UserBulkOrder,
    UserBulkOrdersReader,
    UserBulkOrderWsMessage,
)
from ._user_fund_history import (
    FundMovementType,
    UserFund,
    UserFundHistoryReader,
    UserFundHistoryResponse,
)
from ._user_funding_history import (
    UserFunding,
    UserFundingHistoryReader,
    UserFundingHistoryResponse,
)
from ._user_notifications import (
    NotificationMetadata,
    NotificationType,
    UserNotificationsReader,
    UserNotificationWsMessage,
)
from ._user_open_orders import (
    UserOpenOrder,
    UserOpenOrdersReader,
    UserOpenOrdersResponse,
    UserOpenOrdersWsMessage,
)
from ._user_order_history import (
    UserOrder,
    UserOrderHistoryReader,
    UserOrders,
    UserOrdersWsMessage,
)
from ._user_positions import (
    UserPosition,
    UserPositionsReader,
    UserPositionsWsMessage,
)
from ._user_subaccounts import UserSubaccount, UserSubaccountsReader
from ._user_trade_history import (
    UserTrade,
    UserTradeAction,
    UserTradeHistoryReader,
    UserTradesResponse,
    UserTradesWsMessage,
)
from ._user_twap_history import UserTwapHistoryReader, UserTwapHistoryResponse
from ._vaults import (
    UserOwnedVault,
    UserOwnedVaultsResponse,
    UserPerformanceOnVault,
    Vault,
    VaultDeposit,
    VaultsReader,
    VaultsResponse,
    VaultType,
    VaultWithdrawal,
)
from ._ws import DecibelWsSubscription, Unsubscribe

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._constants import DecibelConfig


class DecibelReadDex:
    def __init__(
        self,
        config: DecibelConfig,
        *,
        api_key: str | None = None,
        on_ws_error: Callable[[Exception], None] | None = None,
    ) -> None:
        aptos = RestClient(config.fullnode_url)
        ws = DecibelWsSubscription(config, api_key, on_ws_error)
        deps = ReaderDeps(config=config, ws=ws, aptos=aptos, api_key=api_key)

        self.ws = ws
        self.account_overview = AccountOverviewReader(deps)
        self.candlesticks = CandlesticksReader(deps)
        self.delegations = DelegationsReader(deps)
        self.leaderboard = LeaderboardReader(deps)
        self.markets = MarketsReader(deps)
        self.market_prices = MarketPricesReader(deps)
        self.market_depth = MarketDepthReader(deps)
        self.market_trades = MarketTradesReader(deps)
        self.market_contexts = MarketContextsReader(deps)
        self.portfolio_chart = PortfolioChartReader(deps)
        self.user_positions = UserPositionsReader(deps)
        self.user_open_orders = UserOpenOrdersReader(deps)
        self.user_order_history = UserOrderHistoryReader(deps)
        self.user_trade_history = UserTradeHistoryReader(deps)
        self.user_bulk_orders = UserBulkOrdersReader(deps)
        self.user_subaccounts = UserSubaccountsReader(deps)
        self.user_fund_history = UserFundHistoryReader(deps)
        self.user_funding_history = UserFundingHistoryReader(deps)
        self.user_active_twaps = UserActiveTwapsReader(deps)
        self.user_twap_history = UserTwapHistoryReader(deps)
        self.user_notifications = UserNotificationsReader(deps)
        self.vaults = VaultsReader(deps)
        self.trading_points = TradingPointsReader(deps)


__all__ = [
    "AccountOverview",
    "AccountOverviewWsMessage",
    "ActivateVaultArgs",
    "AllMarketPricesWsMessage",
    "AssetType",
    "BalanceTable",
    "Candlestick",
    "CandlestickInterval",
    "CandlestickWsMessage",
    "CollateralBalanceSheet",
    "CreateVaultArgs",
    "CrossedPosition",
    "DecibelReadDex",
    "Delegation",
    "DepositToVaultArgs",
    "FundMovementType",
    "GlobalAccountsState",
    "GlobalAccountsStateV1",
    "LeaderboardItem",
    "LeaderboardResponse",
    "LeaderboardSortKey",
    "LiquidationConfigV1",
    "MarketContext",
    "MarketDepth",
    "MarketDepthAggregationSize",
    "MarketDepthWsMessage",
    "MarketMode",
    "MarketModeConfig",
    "MarketOrder",
    "MarketPrice",
    "MarketPriceWsMessage",
    "MarketTrade",
    "MarketTradesResponse",
    "MarketTradeWsMessage",
    "NotificationMetadata",
    "NotificationType",
    "OwnerTradingPoints",
    "PerpMarket",
    "PerpMarketConfig",
    "PerpPosition",
    "PortfolioChartItem",
    "PortfolioChartTimeRange",
    "PortfolioChartType",
    "Precision",
    "Store",
    "StoreExtendRef",
    "SubaccountPoints",
    "SzPrecision",
    "TradingPointsReader",
    "TwapStatus",
    "Unsubscribe",
    "UserActiveTwap",
    "UserActiveTwapsWsMessage",
    "UserBulkOrder",
    "UserBulkOrderWsMessage",
    "UserFund",
    "UserFundHistoryResponse",
    "UserFunding",
    "UserFundingHistoryResponse",
    "UserNotificationWsMessage",
    "UserOpenOrder",
    "UserOpenOrdersResponse",
    "UserOpenOrdersWsMessage",
    "UserOrder",
    "UserOrders",
    "UserOrdersWsMessage",
    "UserOwnedVault",
    "UserOwnedVaultsResponse",
    "UserPerformanceOnVault",
    "UserPosition",
    "UserPositionsWsMessage",
    "UserSubaccount",
    "UserTrade",
    "UserTradeAction",
    "UserTradesResponse",
    "UserTradesWsMessage",
    "UserTwapHistoryResponse",
    "Vault",
    "VaultDeposit",
    "VaultsResponse",
    "VaultType",
    "VaultWithdrawal",
    "VolumeWindow",
    "WithdrawFromVaultArgs",
]
