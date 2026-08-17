from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "CampaignClaim",
    "CampaignMetadata",
    "CampaignStatusName",
    "CampaignSummary",
    "CampaignTypeName",
    "CampaignsReader",
    "TypeBreakdown",
    "WeeklyEarning",
]

CampaignTypeName = Literal[
    "fee_rebate",
    "maker_incentive",
    "liquidation_rebate",
    "volume_milestone",
    "first_funded_trial",
]

CampaignStatusName = Literal[
    "draft",
    "funded",
    "active",
    "expired",
    "reclaimed",
    "cancelled",
]


class CampaignMetadata(BaseModel):
    """A campaign's public definition, as served by ``/api/v1/campaigns/active``."""

    model_config = ConfigDict(populate_by_name=True)

    campaign_id: int
    campaign_type: CampaignTypeName
    status: CampaignStatusName
    title: str
    reward_asset: str
    start_ts_sec: int
    end_ts_sec: int
    claim_start_ts_sec: int
    claim_end_ts_sec: int
    total_funded: float
    description: str | None = None


class CampaignClaim(BaseModel):
    """One campaign plus this account's allocation and claim state against it.

    Amounts are raw u64 chain units — divide by ``10 ** 6`` for USDC. ``ready_to_claim`` is
    ``claimable_amount - claimed_amount -`` anything in flight, so it's the number to put behind
    a "Claim $X" button.
    """

    model_config = ConfigDict(populate_by_name=True)

    campaign_id: int
    campaign_type: CampaignTypeName
    status: CampaignStatusName
    title: str
    reward_asset: str
    start_ts_sec: int
    end_ts_sec: int
    claim_start_ts_sec: int
    claim_end_ts_sec: int
    total_funded: float
    description: str | None = None
    has_allocation: bool
    claimable_amount: float
    claimed_amount: float
    ready_to_claim: float
    claimed_at_ts_sec: int | None = None
    claim_tx_hash: str | None = None


class WeeklyEarning(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    week_start_ts_sec: int
    reward_amount: float


class TypeBreakdown(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    campaign_type: CampaignTypeName
    lifetime_earned: float
    ready_to_claim: float
    total_claimed: float


class CampaignSummary(BaseModel):
    """An account's campaign rewards across every campaign it has an allocation in.

    ``lifetime_earned == ready_to_claim + total_claimed``. ``weekly_wow_bps`` is cumulative
    week-over-week growth in basis points, and is ``0`` when the prior cumulative was ``0`` or
    growth was non-positive.
    """

    model_config = ConfigDict(populate_by_name=True)

    lifetime_earned: float
    ready_to_claim: float
    total_claimed: float
    breakdown_by_type: list[TypeBreakdown]
    claims: list[CampaignClaim]
    year_to_date: float
    weekly_wow_bps: float
    weekly_breakdown: list[WeeklyEarning]
    total_claims: int


class _ActiveCampaigns(RootModel[list[CampaignMetadata]]):
    pass


class CampaignsReader(BaseReader):
    async def get_active(self) -> list[CampaignMetadata]:
        """Every campaign currently visible to users, whatever their allocation."""
        response, _, _ = await self.get_request(
            model=_ActiveCampaigns,
            url=f"{self.config.trading_http_url}/api/v1/campaigns/active",
        )
        return response.root

    async def get_summary(
        self,
        *,
        account_address: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> CampaignSummary:
        """This account's campaign earnings, claim state, and weekly breakdown.

        ``limit`` / ``offset`` paginate the ``claims`` list; the aggregate totals cover every
        campaign regardless of the page.
        """
        params: dict[str, str] = {"account": account_address}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        response, _, _ = await self.get_request(
            model=CampaignSummary,
            url=f"{self.config.trading_http_url}/api/v1/campaigns/account",
            params=params,
        )
        return response
