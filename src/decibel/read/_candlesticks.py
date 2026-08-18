from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, RootModel

from .._asset_type import AssetTypeName
from .._utils import get_market_addr_for_product
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._ws import Unsubscribe

__all__ = [
    "Candlestick",
    "CandlestickInterval",
    "CandlesticksReader",
    "CandlestickWsMessage",
]


class CandlestickInterval(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1mo"


class Candlestick(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    time_end: int = Field(alias="T")
    close: float = Field(alias="c")
    high: float = Field(alias="h")
    interval: str = Field(alias="i")
    low: float = Field(alias="l")
    open_price: float = Field(alias="o")
    time_start: int = Field(alias="t")
    volume: float = Field(alias="v")


class _CandlesticksList(RootModel[list[Candlestick]]):
    pass


class CandlestickWsMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    candle: Candlestick


class CandlesticksReader(BaseReader):
    async def get_by_name(
        self,
        market_name: str,
        *,
        interval: CandlestickInterval,
        start_time: int,
        end_time: int,
        hide_outliers: bool = False,
        asset_type: AssetTypeName = AssetTypeName.PERP,
    ) -> list[Candlestick]:
        """Get candlesticks for a market during a time period.

        The market address is derived from the name per product (perp and spot derive different
        addresses for the same name) — pass ``asset_type=AssetTypeName.SPOT`` for spot markets,
        or prefer :meth:`get_by_addr` when you already hold the market row.
        """
        market_addr = get_market_addr_for_product(market_name, asset_type, self.config.deployment)
        return await self.get_by_addr(
            market_addr,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            hide_outliers=hide_outliers,
        )

    async def get_by_addr(
        self,
        market_addr: str,
        *,
        interval: CandlestickInterval,
        start_time: int,
        end_time: int,
        hide_outliers: bool = False,
    ) -> list[Candlestick]:
        """Get candlesticks by market object address — no name derivation, product-agnostic."""
        params: dict[str, str] = {
            "market": market_addr,
            "interval": interval.value,
            "startTime": str(start_time),
            "endTime": str(end_time),
        }
        if hide_outliers:
            params["filterWicks"] = "true"
            params["nSigma"] = "3.0"

        response, _, _ = await self.get_request(
            model=_CandlesticksList,
            url=f"{self.config.trading_http_url}/api/v1/candlesticks",
            params=params,
        )
        return response.root

    def subscribe_by_name(
        self,
        market_name: str,
        interval: CandlestickInterval,
        on_data: (
            Callable[[CandlestickWsMessage], None]
            | Callable[[CandlestickWsMessage], Awaitable[None]]
        ),
        asset_type: AssetTypeName = AssetTypeName.PERP,
    ) -> Unsubscribe:
        market_addr = get_market_addr_for_product(market_name, asset_type, self.config.deployment)
        return self.subscribe_by_addr(market_addr, interval, on_data)

    def subscribe_by_addr(
        self,
        market_addr: str,
        interval: CandlestickInterval,
        on_data: (
            Callable[[CandlestickWsMessage], None]
            | Callable[[CandlestickWsMessage], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        """Subscribe to candlesticks by market object address — product-agnostic."""
        topic = f"market_candlestick:{market_addr}:{interval.value}"
        return self.ws.subscribe(topic, CandlestickWsMessage, on_data)
