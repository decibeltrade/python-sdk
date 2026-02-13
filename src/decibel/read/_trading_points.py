from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "OwnerTradingPoints",
    "SubaccountPoints",
    "TradingPointsReader",
]


class SubaccountPoints(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    points: float


class OwnerTradingPoints(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owner: str
    total_points: float
    breakdown: list[SubaccountPoints] | None


class TradingPointsReader(BaseReader):
    async def get_by_owner(self, *, owner_addr: str) -> OwnerTradingPoints:
        response, _, _ = await self.get_request(
            model=OwnerTradingPoints,
            url=f"{self.config.trading_http_url}/api/v1/points/trading/account",
            params={"owner": owner_addr},
        )
        return response
