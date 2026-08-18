from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "DailyUserVolume",
    "FeeSchedule",
    "FeeTiers",
    "MarketMakerTier",
    "ProductFeeState",
    "UserFees",
    "UserFeesReader",
    "VipTier",
    "VolumeWeights",
]


class DailyUserVolume(BaseModel):
    """Per-day trading volume entry for the current on-chain fee window."""

    model_config = ConfigDict(populate_by_name=True)

    #: Date in YYYY-MM-DD format (UTC).
    date: str
    #: Total volume (USD, whole-dollar integer string).
    volume: str
    maker_volume: str
    taker_volume: str


class VipTier(BaseModel):
    """A single VIP (volume-based) fee tier.

    Users qualify once their on-chain fee-window volume reaches ``volume_threshold`` USD
    (inclusive, matching the on-chain ``>=``).
    """

    model_config = ConfigDict(populate_by_name=True)

    volume_threshold: str
    #: Taker fee rate at this tier (decimal, e.g. 0.000300 = 0.03%).
    taker: float
    #: Maker fee rate at this tier (decimal, e.g. 0.000090 = 0.009%).
    maker: float


class MarketMakerTier(BaseModel):
    """A single market-maker rebate tier (the list is empty when rebates are disabled)."""

    model_config = ConfigDict(populate_by_name=True)

    #: Fraction of global volume the user must provide as maker (decimal string, e.g. "0.005").
    maker_fraction_threshold: str
    #: Maker rebate rate (negative decimal, e.g. -0.000010).
    maker: float


class FeeTiers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    #: Volume-based VIP tiers above the base (tier 0 rates live on the parent schedule).
    vip: list[VipTier]
    market_maker: list[MarketMakerTier]


class FeeSchedule(BaseModel):
    """Fee schedule mirroring the current on-chain default tiers. Account-independent."""

    model_config = ConfigDict(populate_by_name=True)

    #: Base taker fee (tier 0, no volume requirement), decimal e.g. 0.000340.
    taker: float
    #: Base maker fee (tier 0, no volume requirement), decimal e.g. 0.000110.
    maker: float
    tiers: FeeTiers
    #: Referral discount fraction applied to referred users (0.0 when disabled).
    referral_discount: float


class ProductFeeState(BaseModel):
    """Per-product (perp or spot) fee state.

    Holds the product's own rate ladder, the user's effective rates at the shared cross-product
    tier, and the product's raw (unweighted) volume history.
    """

    model_config = ConfigDict(populate_by_name=True)

    #: This product's fee tier index (0 = base). Perp's tier comes from perp-only window volume;
    #: spot's from the *weighted* cross-product volume, so the two can differ for one user.
    fee_tier: int
    #: Rate ladder for THIS product (spot bps differ from perp at every tier).
    fee_schedule: FeeSchedule
    user_taker_rate: float
    user_maker_rate: float
    #: This product's own daily volume history for the fee window (raw USD, NOT weighted).
    daily_user_volume: list[DailyUserVolume]
    total_window_volume_usd: str
    #: Product-specific referral discount (0.0 for spot, which has no referral program).
    active_referral_discount: float


class VolumeWeights(BaseModel):
    """Cross-product volume multipliers used to compute the unified fee tier.

    Mirrors the on-chain ``CrossProductVolumeWeights`` (100 == 1.0x).
    """

    model_config = ConfigDict(populate_by_name=True)

    perp: float
    spot: float


class UserFees(BaseModel):
    """Response for ``GET /api/v1/user_fee_rates?account=<address>``.

    The fee tier is cross-product: computed from
    ``perp_volume * volume_weights.perp + spot_volume * volume_weights.spot`` and indexed into
    each product's own rate ladder. The top-level fields remain perp-only aliases of ``perp.*``
    for backward compatibility; new consumers should read ``perp`` / ``spot`` explicitly.
    """

    model_config = ConfigDict(populate_by_name=True)

    account: str
    daily_user_volume: list[DailyUserVolume]
    fee_schedule: FeeSchedule
    user_taker_rate: float
    user_maker_rate: float
    fee_tier: int
    active_referral_discount: float
    # The per-product blocks are still rolling out server-side, so they stay optional.
    perp: ProductFeeState | None = None
    spot: ProductFeeState | None = None
    #: Weighted cross-product volume driving ``spot.fee_tier`` (USD, whole-dollar integer string).
    weighted_volume_usd: str | None = None
    volume_weights: VolumeWeights | None = None


class UserFeesReader(BaseReader):
    async def get_by_addr(self, sub_addr: str) -> UserFees:
        """The user's fee rates and the full fee schedule for a subaccount.

        Returns the effective maker/taker rates, the current fee tier (based on the on-chain fee
        window), the full schedule for all VIP tiers, and the daily volume history for that same
        window. Fee rates are decimals (e.g. 0.000340 = 0.034%).
        """
        response, _, _ = await self.get_request(
            model=UserFees,
            url=f"{self.config.trading_http_url}/api/v1/user_fee_rates",
            params={"account": sub_addr},
        )
        return response
