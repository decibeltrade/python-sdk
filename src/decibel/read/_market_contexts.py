from __future__ import annotations

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "MarketContext",
    "MarketContextsReader",
]


class MarketContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    volume_24h: float
    open_interest: float
    previous_day_price: float
    price_change_pct_24h: float


class _MarketContextList(RootModel[list[MarketContext]]):
    pass


class MarketContextsReader(BaseReader):
    async def get_all(self) -> list[MarketContext]:
        # TODO: Update endpoint when API changes to /market_contexts
        # NOTE: marketName filtering is not yet supported by the API
        response, _, _ = await self.get_request(
            model=_MarketContextList,
            url=f"{self.config.trading_http_url}/api/v1/asset_contexts",
        )
        return response.root
