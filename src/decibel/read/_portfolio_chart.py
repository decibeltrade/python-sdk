from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "PortfolioChartItem",
    "PortfolioChartReader",
    "PortfolioChartTimeRange",
    "PortfolioChartType",
]

PortfolioChartType = Literal["pnl", "account_value"]
PortfolioChartTimeRange = Literal["24h", "7d", "30d", "90d"]


class PortfolioChartItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timestamp: int
    data_points: float


class _PortfolioChartList(RootModel[list[PortfolioChartItem]]):
    pass


class PortfolioChartReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        time_range: PortfolioChartTimeRange,
        data_type: PortfolioChartType,
    ) -> list[PortfolioChartItem]:
        response, _, _ = await self.get_request(
            model=_PortfolioChartList,
            url=f"{self.config.trading_http_url}/api/v1/portfolio_chart",
            params={
                "account": sub_addr,
                "range": time_range,
                "data_type": data_type,
            },
        )
        return response.root
