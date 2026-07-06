from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "AccountReferral",
    "AffiliateCode",
    "AffiliateCodesResponse",
    "AffiliateEarningsBreakdown",
    "AffiliateEarningsResponse",
    "AffiliateReferredUser",
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


class AffiliateReferredUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    level: Literal["L1", "L2"]
    referred_by: str | None = None
    total_amps: float
    affiliate_amps_earned: float
    total_volume: float
    active: bool


class AffiliateEarningsBreakdown(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    l1_amps: float
    l2_amps: float
    total_amps: float
    l1_count: int
    l2_count: int


class _AffiliateEarningsUsers(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AffiliateReferredUser]
    total_count: int


class AffiliateEarningsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    affiliate_account: str
    is_affiliate: bool
    earnings: AffiliateEarningsBreakdown
    users: _AffiliateEarningsUsers


class _UserReferralsResponse(RootModel[list[UserReferral]]):
    pass


class ReferralsReader(BaseReader):
    """Read referral codes, account referrals, and affiliate stats/earnings."""

    async def validate_code(self, code: str) -> ReferralCodeValidation:
        """Validate a referral code (existence and active status).

        GET ``/api/v1/referrals/code/{code}``.
        """
        response, _, _ = await self.get_request(
            model=ReferralCodeValidation,
            url=f"{self.config.trading_http_url}/api/v1/referrals/code/{quote(code)}",
        )
        return response

    async def get_account_referral(self, account: str) -> AccountReferral:
        """Return referral information for a specific account.

        GET ``/api/v1/referrals/account/{account}``.
        """
        response, _, _ = await self.get_request(
            model=AccountReferral,
            url=f"{self.config.trading_http_url}/api/v1/referrals/account/{account}",
        )
        return response

    async def redeem_code(self, *, referral_code: str, account: str) -> RedeemReferralResponse:
        """Redeem a referral code for an account.

        POST ``/api/v1/referrals/redeem``.
        """
        response, _, _ = await self.post_request(
            model=RedeemReferralResponse,
            url=f"{self.config.trading_http_url}/api/v1/referrals/redeem",
            body={"referral_code": referral_code, "account": account},
        )
        return response

    async def get_referrer_stats(self, account: str) -> ReferrerStats:
        """Return aggregate referral statistics for a referrer.

        GET ``/api/v1/referrals/stats/{account}``.
        """
        response, _, _ = await self.get_request(
            model=ReferrerStats,
            url=f"{self.config.trading_http_url}/api/v1/referrals/stats/{account}",
        )
        return response

    async def get_user_referrals(
        self,
        *,
        referrer_account: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[UserReferral]:
        """Return the (paginated) list of users referred by a referrer.

        GET ``/api/v1/referrals/users``.
        """
        params: dict[str, str] = {"referrer_account": referrer_account}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        response, _, _ = await self.get_request(
            model=_UserReferralsResponse,
            url=f"{self.config.trading_http_url}/api/v1/referrals/users",
            params=params,
        )
        return response.root

    async def get_affiliate_codes(self, account: str) -> AffiliateCodesResponse:
        """Return all referral codes owned by an account with per-code usage stats.

        GET ``/api/v1/affiliates/codes/{account}``.
        """
        response, _, _ = await self.get_request(
            model=AffiliateCodesResponse,
            url=f"{self.config.trading_http_url}/api/v1/affiliates/codes/{account}",
        )
        return response

    async def get_affiliate_earnings(self, account: str) -> AffiliateEarningsResponse:
        """Return the affiliate earnings breakdown and referred users for an account.

        GET ``/api/v1/affiliates/earnings/{account}``.
        """
        response, _, _ = await self.get_request(
            model=AffiliateEarningsResponse,
            url=f"{self.config.trading_http_url}/api/v1/affiliates/earnings/{account}",
            params={"limit": "1000"},
        )
        return response
