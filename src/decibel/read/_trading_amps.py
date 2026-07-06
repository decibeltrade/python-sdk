from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "OwnerTradingAmps",
    "SubaccountAmps",
    "TradingAmpsReader",
]


class SubaccountAmps(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    total_amps: float


class OwnerTradingAmps(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owner: str
    total_amps: float
    breakdown: list[SubaccountAmps] | None = None


class TradingAmpsReader(BaseReader):
    async def get_by_owner(
        self,
        *,
        owner_addr: str,
        season: str | None = None,
        days: int | None = None,
    ) -> OwnerTradingAmps:
        params: dict[str, str] = {"owner": owner_addr}
        if season is not None:
            params["season"] = season
        if days is not None:
            params["days"] = str(days)
        response, _, _ = await self.get_request(
            model=OwnerTradingAmps,
            url=f"{self.config.trading_http_url}/api/v1/points/trading/amps",
            params=params,
        )
        return response
