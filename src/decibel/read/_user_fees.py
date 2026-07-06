from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "DailyUserVolume",
    "FeeSchedule",
    "FeeTiers",
    "MarketMakerTier",
    "UserFees",
    "UserFeesReader",
    "VipTier",
]


class DailyUserVolume(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    volume: str
    maker_volume: str
    taker_volume: str


class VipTier(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    volume_threshold: str
    taker: float
    maker: float


class MarketMakerTier(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    maker_fraction_threshold: str
    maker: float


class FeeTiers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vip: list[VipTier]
    market_maker: list[MarketMakerTier]


class FeeSchedule(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    taker: float
    maker: float
    tiers: FeeTiers
    referral_discount: float


class UserFees(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    daily_user_volume: list[DailyUserVolume]
    fee_schedule: FeeSchedule
    user_taker_rate: float
    user_maker_rate: float
    fee_tier: int
    active_referral_discount: float


class UserFeesReader(BaseReader):
    async def get_by_addr(self, *, sub_addr: str) -> UserFees:
        response, _, _ = await self.get_request(
            model=UserFees,
            url=f"{self.config.trading_http_url}/api/v1/user_fee_rates",
            params={"account": sub_addr},
        )
        return response
