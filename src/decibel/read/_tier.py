from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "TierInfo",
    "TierReader",
    "TierThreshold",
]


class TierThreshold(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    hz_threshold: float
    progress: float


class TierInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owner: str
    total_amps: float
    rank: int | None = None
    current_tier: str | None = None
    tiers: list[TierThreshold]


class TierReader(BaseReader):
    async def get_by_owner(self, owner_addr: str) -> TierInfo:
        """Tier info for an owner, with progress toward each percentile-based threshold."""
        response, _, _ = await self.get_request(
            model=TierInfo,
            url=f"{self.config.trading_http_url}/api/v1/points/tier",
            params={"owner": owner_addr},
        )
        return response
