from __future__ import annotations

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "SpotAssetContext",
    "SpotAssetContextsReader",
]


class SpotAssetContext(BaseModel):
    """24h stats + current price snapshot for one spot market.

    The spot counterpart of the perp asset contexts. Perp-only concepts (funding, open
    interest, mark/oracle prices) are deliberately absent.

    Null semantics: ``last_price``/``high_24h``/``low_24h`` are ``None`` when the market had no
    trades in the last 24h; ``mid`` is ``None`` unless both book sides have resting liquidity;
    ``prev_day_price`` is ``None`` for markets that never traded before the 24h boundary
    (render 24h change as n/a). 24h change = ``(last_price - prev_day_price) / prev_day_price``,
    derived client-side.
    """

    model_config = ConfigDict(populate_by_name=True)

    market_addr: str
    name: str
    ticker_id: str
    base_asset_addr: str
    quote_asset_addr: str
    base_decimals: int
    quote_decimals: int
    last_price: float | None
    mid: float | None
    prev_day_price: float | None
    volume_24h_base: float
    volume_24h_quote: float
    high_24h: float | None
    low_24h: float | None
    timestamp_unix_ms: int


class _SpotAssetContextList(RootModel[list[SpotAssetContext]]):
    pass


class SpotAssetContextsReader(BaseReader):
    async def get_all(self) -> list[SpotAssetContext]:
        """Get 24h stats + current price snapshot for every registered spot market."""
        response, _, _ = await self.get_request(
            model=_SpotAssetContextList,
            url=f"{self.config.trading_http_url}/api/v1/spot/asset_contexts",
        )
        return response.root
