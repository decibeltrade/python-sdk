from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.async_client import RestClient

from .._constants import HTTP_LIMITS, HTTP_TIMEOUT
from ._account_overview import (
    AccountOverview,
    AccountOverviewReader,
    AccountOverviewWsMessage,
    VolumeWindow,
)
from ._base import ReaderDeps
from ._campaigns import (
    CampaignClaim,
    CampaignMetadataHttp,
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
from ._points_leaderboard import (
    PointsLeaderboardItem,
    PointsLeaderboardReader,
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
    AffiliateCodesResponse,
    AffiliateEarningsBreakdown,
    AffiliateEarningsResponse,
    AffiliateReferredUser,
    RedeemReferralResponse,
    ReferralCodeSource,
    ReferralCodeValidation,
    ReferralsReader,
    ReferrerStats,
    UserReferral,
)
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
    UserBulkOrdersReader,
    UserBulkOrderWsMessage,
)
from ._user_fees import (
    DailyUserVolume,
    FeeSchedule,
    FeeTiers,
    MarketMakerTier,
    UserFees,
    UserFeesReader,
    VipTier,
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
        self._config = config
        self._aptos = aptos
        self._usdc_decimals_cache: int | None = None
        deps = ReaderDeps(
            config=config,
            ws=ws,
            aptos=aptos,
            api_key=api_key,
            http_client=self._http_client,
        )

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
        self.campaigns = CampaignsReader(deps)
        self.points_leaderboard = PointsLeaderboardReader(deps)
        self.streaks = StreaksReader(deps)
        self.trading_amps = TradingAmpsReader(deps)
        self.tier = TierReader(deps)
        self.global_points_stats = GlobalPointsStatsReader(deps)
        self.referrals = ReferralsReader(deps)
        self.user_fees = UserFeesReader(deps)
        self.withdraw_queue = WithdrawQueueReader(deps)

    # -----------------------------------------------------------------
    # On-chain view / resource helpers
    # -----------------------------------------------------------------
    async def _view(
        self,
        function: str,
        type_arguments: list[str],
        arguments: list[Any],
    ) -> list[Any]:
        result_bytes = await self._aptos.view(function, type_arguments, arguments)
        return json.loads(result_bytes.decode("utf-8"))

    async def global_perp_engine_state(self) -> dict[str, Any] | bool:
        """Return the global perp_engine state resource, or False if unavailable."""
        pkg = self._config.deployment.package
        try:
            return await self._aptos.account_resource(
                AccountAddress.from_str(pkg),
                f"{pkg}::perp_engine::Global",
            )
        except Exception:
            return False

    async def collateral_balance_decimals(self) -> int:
        pkg = self._config.deployment.package
        result = await self._view(f"{pkg}::perp_engine::collateral_balance_decimals", [], [])
        return int(result[0])

    async def usdc_decimals(self) -> int:
        if self._usdc_decimals_cache is not None:
            return self._usdc_decimals_cache
        result = await self._view(
            "0x1::fungible_asset::decimals",
            ["0x1::fungible_asset::Metadata"],
            [self._config.deployment.usdc],
        )
        self._usdc_decimals_cache = int(result[0])
        return self._usdc_decimals_cache

    async def usdc_balance(self, addr: str | AccountAddress) -> float:
        usdc_decimals = await self.usdc_decimals()
        result = await self._view(
            "0x1::primary_fungible_store::balance",
            ["0x1::fungible_asset::Metadata"],
            [str(addr), self._config.deployment.usdc],
        )
        return int(result[0]) / 10**usdc_decimals

    async def token_balance(
        self,
        addr: str | AccountAddress,
        token_addr: str | AccountAddress,
        token_decimals: int,
    ) -> float:
        result = await self._view(
            "0x1::primary_fungible_store::balance",
            ["0x1::fungible_asset::Metadata"],
            [str(addr), str(token_addr)],
        )
        return int(result[0]) / 10**token_decimals

    async def account_balance(self, addr: str | AccountAddress) -> int:
        """Return the account's total cross collateral value (raw chain units)."""
        pkg = self._config.deployment.package
        result = await self._view(
            f"{pkg}::perp_engine::get_cross_total_collateral_value",
            [],
            [str(addr)],
        )
        return int(result[0])

    async def position_size(
        self,
        addr: str | AccountAddress,
        market_addr: str,
    ) -> list[Any]:
        """Return the position size view result for an account in a market."""
        pkg = self._config.deployment.package
        return await self._view(
            f"{pkg}::perp_engine::get_position_size",
            [],
            [str(addr), market_addr],
        )

    async def get_crossed_position(self, addr: str | AccountAddress) -> CrossedPosition | None:
        """Return the crossed position resource for an account, or None if absent."""
        pkg = self._config.deployment.package
        creator = addr if isinstance(addr, AccountAddress) else AccountAddress.from_str(addr)
        crossed_position_addr = AccountAddress.for_named_object(creator, b"perp_position")
        try:
            resource = await self._aptos.account_resource(
                crossed_position_addr,
                f"{pkg}::perp_positions::CrossedPosition",
            )
            return CrossedPosition.model_validate(resource)
        except Exception:
            return None

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
    "AccountOverview",
    "AccountOverviewWsMessage",
    "AccountReferral",
    "AccountStreaks",
    "AffiliateCode",
    "AffiliateCodesResponse",
    "AffiliateEarningsBreakdown",
    "AffiliateEarningsResponse",
    "AffiliateReferredUser",
    "CampaignClaim",
    "CampaignMetadataHttp",
    "CampaignStatusName",
    "CampaignSummary",
    "CampaignTypeName",
    "CampaignsReader",
    "DailyUserVolume",
    "FeeSchedule",
    "FeeTiers",
    "GlobalPointsStats",
    "GlobalPointsStatsReader",
    "KnownWithdrawCancelReason",
    "MarketMakerTier",
    "OwnerTradingAmps",
    "PendingWithdrawRequest",
    "PointsLeaderboardItem",
    "PointsLeaderboardReader",
    "PointsLeaderboardSortKey",
    "PointsLeaderboardTierFilter",
    "RedeemReferralResponse",
    "ReferralCodeSource",
    "ReferralCodeValidation",
    "ReferralsReader",
    "ReferrerStats",
    "StreaksReader",
    "SubaccountAmps",
    "TierInfo",
    "TierReader",
    "TierThreshold",
    "TradingAmpsReader",
    "TypeBreakdown",
    "UserFees",
    "UserFeesReader",
    "UserReferral",
    "VipTier",
    "WeeklyEarning",
    "WithdrawQueueEntry",
    "WithdrawQueueReader",
    "WithdrawQueueResponse",
    "WithdrawQueueStatus",
    "WithdrawQueueUpdate",
    "is_known_cancel_reason",
    "merge_withdraw_queue_entries",
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
