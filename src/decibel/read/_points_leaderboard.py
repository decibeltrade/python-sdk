from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .._pagination import PaginatedResponse
from ._base import BaseReader

__all__ = [
    "PointsLeaderboardItem",
    "PointsLeaderboardReader",
    "PointsLeaderboardSortKey",
    "PointsLeaderboardTierFilter",
]

PointsLeaderboardSortKey = Literal["total_amps", "realized_pnl"]
PointsLeaderboardTierFilter = Literal["top20", "diamond", "doublePlatinum", "gold"]


class PointsLeaderboardItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rank: int
    owner: str
    total_amps: float
    realized_pnl: float
    referral_amps: float
    vault_amps: float
    streak_amps: float
    bonus_amps: float = 0


class PointsLeaderboardReader(BaseReader):
    async def get_points_leaderboard(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        search_term: str | None = None,
        sort_key: PointsLeaderboardSortKey | None = None,
        sort_dir: Literal["ASC", "DESC"] | None = None,
        tier: PointsLeaderboardTierFilter | None = None,
    ) -> PaginatedResponse[PointsLeaderboardItem]:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if search_term is not None:
            params["search_term"] = search_term
        if sort_key is not None:
            params["sort_key"] = sort_key
        if sort_dir is not None:
            params["sort_dir"] = sort_dir
        if tier is not None:
            params["tier"] = tier

        response, _, _ = await self.get_request(
            model=PaginatedResponse[PointsLeaderboardItem],
            url=f"{self.config.trading_http_url}/api/v1/points_leaderboard",
            params=params if params else None,
        )
        return response
