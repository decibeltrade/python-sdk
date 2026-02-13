from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "LeaderboardItem",
    "LeaderboardReader",
    "LeaderboardResponse",
    "LeaderboardSortKey",
]

LeaderboardSortKey = Literal["volume", "realized_pnl", "roi", "account_value"]


class LeaderboardItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rank: int
    account: str
    account_value: float
    realized_pnl: float
    roi: float
    volume: float


class LeaderboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[LeaderboardItem]
    total_count: int


class LeaderboardReader(BaseReader):
    async def get_leaderboard(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        search_term: str | None = None,
        sort_key: LeaderboardSortKey | None = None,
        sort_dir: Literal["ASC", "DESC"] | None = None,
    ) -> LeaderboardResponse:
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

        response, _, _ = await self.get_request(
            model=LeaderboardResponse,
            url=f"{self.config.trading_http_url}/api/v1/leaderboard",
            params=params if params else None,
        )
        return response
