from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "CampaignClaim",
    "CampaignMetadataHttp",
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
]

CampaignStatusName = Literal[
    "draft",
    "funded",
    "active",
    "expired",
    "reclaimed",
    "cancelled",
]


class CampaignMetadataHttp(BaseModel):
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
    claimed_at_ts_sec: float | None = None
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
    model_config = ConfigDict(populate_by_name=True)

    lifetime_earned: float
    ready_to_claim: float
    total_claimed: float
    breakdown_by_type: list[TypeBreakdown]
    claims: list[CampaignClaim]
    year_to_date: float
    weekly_wow_bps: float
    weekly_breakdown: list[WeeklyEarning]
    total_claims: float


class _ActiveCampaigns(RootModel[list[CampaignMetadataHttp]]):
    pass


class CampaignsReader(BaseReader):
    """Read reward-campaign metadata and per-account campaign summaries."""

    async def get_active(self) -> list[CampaignMetadataHttp]:
        """Return all currently active reward campaigns.

        GET ``/api/v1/campaigns/active``.
        """
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
        """Return an account's campaign earnings summary and claim history.

        GET ``/api/v1/campaigns/account``. ``limit``/``offset`` page the
        embedded claims list.
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
