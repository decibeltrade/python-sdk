from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, RootModel

from .._utils import get_market_addr
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
    ) -> list[Candlestick]:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)

        response, _, _ = await self.get_request(
            model=_CandlesticksList,
            url=f"{self.config.trading_http_url}/api/v1/candlesticks",
            params={
                "market": market_addr,
                "interval": interval.value,
                "startTime": str(start_time),
                "endTime": str(end_time),
            },
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
    ) -> Unsubscribe:
        market_addr = get_market_addr(market_name, self.config.deployment.perp_engine_global)
        topic = f"market_candlestick:{market_addr}:{interval.value}"
        return self.ws.subscribe(topic, CandlestickWsMessage, on_data)
