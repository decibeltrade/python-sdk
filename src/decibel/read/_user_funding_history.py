from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "UserFunding",
    "UserFundingHistoryReader",
    "UserFundingHistoryResponse",
]


class UserFunding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    market: str
    action: str
    size: float
    is_funding_positive: bool
    realized_funding_amount: float
    is_rebate: bool
    fee_amount: float
    transaction_unix_ms: int


class UserFundingHistoryResponse(BaseModel):
    items: list[UserFunding]
    total_count: int


class UserFundingHistoryReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        limit: int = 10,
        offset: int = 0,
    ) -> UserFundingHistoryResponse:
        response, _, _ = await self.get_request(
            model=UserFundingHistoryResponse,
            url=f"{self.config.trading_http_url}/api/v1/funding_rate_history",
            params={"account": sub_addr, "limit": str(limit), "offset": str(offset)},
        )
        return response
