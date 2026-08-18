from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "GlobalPointsStats",
    "GlobalPointsStatsReader",
]


class GlobalPointsStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_users: int
    total_amps_distributed: float


class GlobalPointsStatsReader(BaseReader):
    async def get(self) -> GlobalPointsStats:
        """Protocol-wide points totals."""
        response, _, _ = await self.get_request(
            model=GlobalPointsStats,
            url=f"{self.config.trading_http_url}/api/v1/points/global",
        )
        return response
