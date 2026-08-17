from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, NamedTuple

import httpx
from aptos_sdk.async_client import RestClient

from .._asset_type import AssetTypeFilter, AssetTypeName, is_spot, to_asset_type_param
from .._constants import HTTP_LIMITS, HTTP_TIMEOUT
from ._account_overview import (
    AccountOverview,
    AccountOverviewReader,
    AccountOverviewWsMessage,
    SecondaryCollateral,
    SpotInFlightOrder,
    SpotMetrics,
    SpotOverview,
    SpotPosition,
    VolumeWindow,
)
from ._base import ReaderDeps
from ._campaigns import (
    CampaignClaim,
    CampaignMetadata,
    CampaignsReader,
    CampaignStatusName,
    CampaignSummary,
    CampaignTypeName,
    TypeBreakdown,
    WeeklyEarning,
)
from ._candlesticks import (
    Candlestick,
    CandlestickInterval,
    CandlesticksReader,
    CandlestickWsMessage,
)
from ._delegations import Delegation, DelegationsReader
from ._funded_first_trade import (
    SOFT_BURN_WARN_RATIO,
    ActiveLock,
    CampaignLocksResponse,
    DailyBurn,
    Eligibility,
    EligibilityInputs,
    FftBlockerCode,
    FundedFirstTradeReader,
    LockDto,
    LockStatus,
    LockTotals,
    OiState,
    ProtectedTrialsResponse,
    ProtectedTrialUpdate,
    SettleReason,
    SoftWarnings,
    TradeSide,
    TrialConfig,
    TrialDto,
    TrialHistoryPage,
    TrialPriorStatus,
    TrialStatus,
    UserCredits,
    compute_eligibility,
)
from ._global_points_stats import GlobalPointsStats, GlobalPointsStatsReader
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
    AllSpotMidsWsMessage,
    MarketPrice,
    MarketPricesReader,
    MarketPriceWsMessage,
    Mid,
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
    is_perp_market,
    is_spot_market,
)
from ._points_leaderboard import (
    PointsLeaderboardItem,
    PointsLeaderboardReader,
    PointsLeaderboardResponse,
    PointsLeaderboardSortKey,
    PointsLeaderboardTierFilter,
)
from ._portfolio_chart import (
    PortfolioChartItem,
    PortfolioChartReader,
    PortfolioChartTimeRange,
    PortfolioChartType,
)
from ._referrals import (
    AccountReferral,
    AffiliateCode,
    AffiliateCodeAnalytics,
    AffiliateCodeAnalyticsResponse,
    AffiliateCodesResponse,
    AffiliateEarningsBreakdown,
    AffiliateEarningsResponse,
    AffiliateReferredUser,
    AffiliateReferredUsers,
    RedeemReferralResponse,
    ReferralCodeSource,
    ReferralCodeValidation,
    ReferralsReader,
    ReferrerStats,
    UserReferral,
)
from ._rwa_insights import (
    RWA_TICKERS,
    RwaAfterHours,
    RwaAnalystRatings,
    RwaDateStatus,
    RwaEarningsQuarter,
    RwaInsights,
    RwaKeyStatistics,
    RwaSession,
    is_rwa_ticker,
)
from ._spot_asset_contexts import SpotAssetContext, SpotAssetContextsReader
from ._streaks import AccountStreaks, StreaksReader
from ._tier import TierInfo, TierReader, TierThreshold
from ._trading_amps import OwnerTradingAmps, SubaccountAmps, TradingAmpsReader
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
    UserBulkOrderFill,
    UserBulkOrderFillsResponse,
    UserBulkOrdersReader,
    UserBulkOrderStatus,
    UserBulkOrderWsMessage,
)
from ._user_fees import (
    DailyUserVolume,
    FeeSchedule,
    FeeTiers,
    MarketMakerTier,
    ProductFeeState,
    UserFees,
    UserFeesReader,
    VipTier,
    VolumeWeights,
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
from ._user_orders import UserOrdersReader, UserOrderUpdate
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
from ._withdraw_queue import (
    KnownWithdrawCancelReason,
    PendingWithdrawRequest,
    WithdrawQueueEntry,
    WithdrawQueueReader,
    WithdrawQueueResponse,
    WithdrawQueueStatus,
    WithdrawQueueUpdate,
    is_known_cancel_reason,
    merge_withdraw_queue_entries,
)
from ._ws import DecibelWsSubscription, Unsubscribe

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._constants import DecibelConfig


class FungibleAssetMetadata(NamedTuple):
    """On-chain fungible-asset metadata, via the ``0x1::fungible_asset`` view functions."""

    name: str
    symbol: str
    decimals: int


class SpotMarketAssets(NamedTuple):
    """Base/quote fungible-asset addresses of a spot market (escrow views)."""

    base_asset_addr: str
    quote_asset_addr: str


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
        self._http_client = httpx.AsyncClient(limits=HTTP_LIMITS, timeout=HTTP_TIMEOUT)
        deps = ReaderDeps(
            config=config,
            ws=ws,
            aptos=aptos,
            api_key=api_key,
            http_client=self._http_client,
        )

        self.ws = ws
        self._config = config
        self._aptos = aptos
        self.account_overview = AccountOverviewReader(deps)
        self.candlesticks = CandlesticksReader(deps)
        self.delegations = DelegationsReader(deps)
        self.leaderboard = LeaderboardReader(deps)
        self.markets = MarketsReader(deps)
        self.market_prices = MarketPricesReader(deps)
        self.market_depth = MarketDepthReader(deps)
        self.market_trades = MarketTradesReader(deps)
        self.market_contexts = MarketContextsReader(deps)
        self.spot_asset_contexts = SpotAssetContextsReader(deps)
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
        self.user_orders = UserOrdersReader(deps)
        self.user_fees = UserFeesReader(deps)
        self.user_notifications = UserNotificationsReader(deps)
        self.withdraw_queue = WithdrawQueueReader(deps)
        self.vaults = VaultsReader(deps)
        self.trading_points = TradingPointsReader(deps)
        self.trading_amps = TradingAmpsReader(deps)
        self.tier = TierReader(deps)
        self.global_points_stats = GlobalPointsStatsReader(deps)
        self.points_leaderboard = PointsLeaderboardReader(deps)
        self.streaks = StreaksReader(deps)
        self.campaigns = CampaignsReader(deps)
        self.referrals = ReferralsReader(deps)
        self.funded_first_trade = FundedFirstTradeReader(deps)

    async def _view(
        self, function: str, type_arguments: list[str], arguments: list[Any]
    ) -> list[Any]:
        result_bytes = await self._aptos.view(function, type_arguments, arguments)
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return result

    async def spot_market_assets(self, market_addr: str) -> SpotMarketAssets:
        """Resolve a spot market's base and quote fungible-asset addresses.

        Reads the on-chain escrow views — ``/api/v1/markets`` doesn't expose these, and they're
        needed to query wallet (primary fungible store) balances for spot order sizing.
        """
        package = self._config.deployment.package
        base, quote = await asyncio.gather(
            self._view(f"{package}::spot_market_escrow::base_asset_metadata", [], [market_addr]),
            self._view(f"{package}::spot_market_escrow::quote_asset_metadata", [], [market_addr]),
        )
        return SpotMarketAssets(
            base_asset_addr=str(base[0]["inner"]),
            quote_asset_addr=str(quote[0]["inner"]),
        )

    async def fungible_asset_metadata(self, asset_addr: str) -> FungibleAssetMetadata:
        """Read on-chain fungible-asset name, symbol, and decimals for any FA address.

        Useful for e.g. the entries in ``account_overview.secondary_collateral``.
        """
        metadata_type = ["0x1::fungible_asset::Metadata"]
        name, symbol, decimals = await asyncio.gather(
            self._view("0x1::fungible_asset::name", metadata_type, [asset_addr]),
            self._view("0x1::fungible_asset::symbol", metadata_type, [asset_addr]),
            self._view("0x1::fungible_asset::decimals", metadata_type, [asset_addr]),
        )
        return FungibleAssetMetadata(
            name=str(name[0]),
            symbol=str(symbol[0]),
            decimals=int(decimals[0]),
        )

    async def close(self) -> None:
        try:
            await self.ws.close()
        finally:
            await self._http_client.aclose()

    async def __aenter__(self) -> DecibelReadDex:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()


__all__ = [
    "RWA_TICKERS",
    "SOFT_BURN_WARN_RATIO",
    "AccountOverview",
    "AccountOverviewWsMessage",
    "AccountReferral",
    "AccountStreaks",
    "ActivateVaultArgs",
    "ActiveLock",
    "AffiliateCode",
    "AffiliateCodeAnalytics",
    "AffiliateCodeAnalyticsResponse",
    "AffiliateCodesResponse",
    "AffiliateEarningsBreakdown",
    "AffiliateEarningsResponse",
    "AffiliateReferredUser",
    "AffiliateReferredUsers",
    "AllMarketPricesWsMessage",
    "AllSpotMidsWsMessage",
    "AssetType",
    "AssetTypeFilter",
    "AssetTypeName",
    "BalanceTable",
    "CampaignClaim",
    "CampaignLocksResponse",
    "CampaignMetadata",
    "CampaignStatusName",
    "CampaignSummary",
    "CampaignTypeName",
    "Candlestick",
    "CandlestickInterval",
    "CandlestickWsMessage",
    "CollateralBalanceSheet",
    "CreateVaultArgs",
    "CrossedPosition",
    "DailyBurn",
    "DailyUserVolume",
    "DecibelReadDex",
    "Delegation",
    "DepositToVaultArgs",
    "Eligibility",
    "EligibilityInputs",
    "FeeSchedule",
    "FeeTiers",
    "FftBlockerCode",
    "FundMovementType",
    "FungibleAssetMetadata",
    "GlobalAccountsState",
    "GlobalAccountsStateV1",
    "GlobalPointsStats",
    "KnownWithdrawCancelReason",
    "LeaderboardItem",
    "LeaderboardResponse",
    "LeaderboardSortKey",
    "LiquidationConfigV1",
    "LockDto",
    "LockStatus",
    "LockTotals",
    "MarketContext",
    "MarketMakerTier",
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
    "Mid",
    "NotificationMetadata",
    "NotificationType",
    "OiState",
    "OwnerTradingAmps",
    "OwnerTradingPoints",
    "PendingWithdrawRequest",
    "PerpMarket",
    "PerpMarketConfig",
    "PerpPosition",
    "PointsLeaderboardItem",
    "PointsLeaderboardResponse",
    "PointsLeaderboardSortKey",
    "PointsLeaderboardTierFilter",
    "PortfolioChartItem",
    "PortfolioChartTimeRange",
    "PortfolioChartType",
    "Precision",
    "ProductFeeState",
    "ProtectedTrialUpdate",
    "ProtectedTrialsResponse",
    "RedeemReferralResponse",
    "ReferralCodeSource",
    "ReferralCodeValidation",
    "ReferrerStats",
    "RwaAfterHours",
    "RwaAnalystRatings",
    "RwaDateStatus",
    "RwaEarningsQuarter",
    "RwaInsights",
    "RwaKeyStatistics",
    "RwaSession",
    "SecondaryCollateral",
    "SettleReason",
    "SoftWarnings",
    "SpotAssetContext",
    "SpotInFlightOrder",
    "SpotMarketAssets",
    "SpotMetrics",
    "SpotOverview",
    "SpotPosition",
    "Store",
    "StoreExtendRef",
    "SubaccountAmps",
    "SubaccountPoints",
    "SzPrecision",
    "TierInfo",
    "TierThreshold",
    "TradeSide",
    "TradingPointsReader",
    "TrialConfig",
    "TrialDto",
    "TrialHistoryPage",
    "TrialPriorStatus",
    "TrialStatus",
    "TwapStatus",
    "TypeBreakdown",
    "Unsubscribe",
    "UserActiveTwap",
    "UserActiveTwapsWsMessage",
    "UserBulkOrder",
    "UserBulkOrderFill",
    "UserBulkOrderFillsResponse",
    "UserBulkOrderStatus",
    "UserBulkOrderWsMessage",
    "UserCredits",
    "UserFees",
    "UserFund",
    "UserFundHistoryResponse",
    "UserFunding",
    "UserFundingHistoryResponse",
    "UserNotificationWsMessage",
    "UserOpenOrder",
    "UserOpenOrdersResponse",
    "UserOpenOrdersWsMessage",
    "UserOrder",
    "UserOrderUpdate",
    "UserOrders",
    "UserOrdersWsMessage",
    "UserOwnedVault",
    "UserOwnedVaultsResponse",
    "UserPerformanceOnVault",
    "UserPosition",
    "UserPositionsWsMessage",
    "UserReferral",
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
    "VipTier",
    "VolumeWeights",
    "VolumeWindow",
    "WeeklyEarning",
    "WithdrawFromVaultArgs",
    "WithdrawQueueEntry",
    "WithdrawQueueResponse",
    "WithdrawQueueStatus",
    "WithdrawQueueUpdate",
    "compute_eligibility",
    "is_known_cancel_reason",
    "is_perp_market",
    "is_rwa_ticker",
    "is_spot",
    "is_spot_market",
    "merge_withdraw_queue_entries",
    "to_asset_type_param",
]
