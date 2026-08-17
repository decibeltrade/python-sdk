from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "AccountReferral",
    "AffiliateCode",
    "AffiliateCodeAnalytics",
    "AffiliateCodeAnalyticsResponse",
    "AffiliateCodesResponse",
    "AffiliateEarningsBreakdown",
    "AffiliateEarningsResponse",
    "AffiliateReferredUser",
    "AffiliateReferredUsers",
    "RedeemReferralResponse",
    "ReferralCodeSource",
    "ReferralCodeValidation",
    "ReferralsReader",
    "ReferrerStats",
    "UserReferral",
]

ReferralCodeSource = Literal["admin", "auto", "reusable", "predeposit", "unknown"]


class ReferralCodeValidation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    referral_code: str
    is_valid: bool
    is_active: bool


class RedeemReferralResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    referral_code: str
    account: str


class AccountReferral(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    referrer_account: str
    referral_code: str
    is_affiliate_referral: bool
    referred_at_ms: int
    is_active: bool


class ReferrerStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    referrer_account: str
    total_referrals: int
    total_codes_created: int
    is_affiliate: bool
    codes: list[str]
    volume_threshold_met: bool


class UserReferral(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    referrer_account: str
    referral_code: str
    is_affiliate_referral: bool
    referred_at_ms: int


class _UserReferrals(RootModel[list[UserReferral]]):
    pass


class AffiliateCode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    referral_code: str
    owner_account: str
    max_usage: int
    usage_count: int
    is_active: bool
    is_affiliate: bool
    source: ReferralCodeSource
    created_at_ms: int


class AffiliateCodesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owner_account: str
    codes: list[AffiliateCode]
    volume_threshold_met: bool


class AffiliateCodeAnalytics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    referral_code: str
    l1_volume_usd: float
    l1_amps_earned: float


class AffiliateCodeAnalyticsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owner_account: str
    codes: list[AffiliateCodeAnalytics]


class AffiliateReferredUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    level: Literal["L1", "L2"]
    referred_by: str | None
    total_amps: float
    affiliate_amps_earned: float
    total_volume: float
    active: bool


class AffiliateReferredUsers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AffiliateReferredUser]
    total_count: int


class AffiliateEarningsBreakdown(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    l1_amps: float
    l2_amps: float
    total_amps: float
    l1_count: int
    l2_count: int


class AffiliateEarningsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    affiliate_account: str
    is_affiliate: bool
    earnings: AffiliateEarningsBreakdown
    users: AffiliateReferredUsers


class ReferralsReader(BaseReader):
    async def validate_code(self, code: str) -> ReferralCodeValidation:
        """Check whether a referral code exists and is still active."""
        response, _, _ = await self.get_request(
            model=ReferralCodeValidation,
            url=f"{self.config.trading_http_url}/api/v1/referrals/code/{quote(code, safe='')}",
        )
        return response

    async def get_account_referral(self, account: str) -> AccountReferral:
        """Which code an account was referred by, and by whom."""
        acct = quote(account, safe="")
        response, _, _ = await self.get_request(
            model=AccountReferral,
            url=f"{self.config.trading_http_url}/api/v1/referrals/account/{acct}",
        )
        return response

    async def redeem_code(self, *, referral_code: str, account: str) -> RedeemReferralResponse:
        """Redeem a referral code for an account."""
        response, _, _ = await self.post_request(
            model=RedeemReferralResponse,
            url=f"{self.config.trading_http_url}/api/v1/referrals/redeem",
            body={"referral_code": referral_code, "account": account},
        )
        return response

    async def get_referrer_stats(self, account: str) -> ReferrerStats:
        """Aggregate referral statistics for a referrer."""
        response, _, _ = await self.get_request(
            model=ReferrerStats,
            url=f"{self.config.trading_http_url}/api/v1/referrals/stats/{quote(account, safe='')}",
        )
        return response

    async def get_user_referrals(
        self,
        *,
        referrer_account: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[UserReferral]:
        """Paginated list of the users a referrer has referred."""
        params: dict[str, str] = {"referrer_account": referrer_account}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        response, _, _ = await self.get_request(
            model=_UserReferrals,
            url=f"{self.config.trading_http_url}/api/v1/referrals/users",
            params=params,
        )
        return response.root

    async def get_affiliate_codes(self, account: str) -> AffiliateCodesResponse:
        """Every referral code an account owns, with per-code usage stats."""
        response, _, _ = await self.get_request(
            model=AffiliateCodesResponse,
            url=f"{self.config.trading_http_url}/api/v1/affiliates/codes/{quote(account, safe='')}",
        )
        return response

    async def get_affiliate_code_analytics(self, account: str) -> AffiliateCodeAnalyticsResponse:
        """Per-code L1 analytics (volume + amps earned) for an account's affiliate codes.

        Split from :meth:`get_affiliate_codes` so the metadata endpoint — hit on every page load
        via the global nav — doesn't pay the analytics JOIN cost.
        """
        acct = quote(account, safe="")
        response, _, _ = await self.get_request(
            model=AffiliateCodeAnalyticsResponse,
            url=f"{self.config.trading_http_url}/api/v1/affiliates/codes/{acct}/analytics",
        )
        return response

    async def get_affiliate_earnings(self, account: str) -> AffiliateEarningsResponse:
        """Affiliate earnings breakdown plus the referred users behind it."""
        acct = quote(account, safe="")
        response, _, _ = await self.get_request(
            model=AffiliateEarningsResponse,
            url=f"{self.config.trading_http_url}/api/v1/affiliates/earnings/{acct}",
            params={"limit": "1000"},
        )
        return response
