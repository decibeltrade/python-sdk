from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ._base import BaseReader

__all__ = [
    "FundMovementType",
    "UserFund",
    "UserFundHistoryReader",
    "UserFundHistoryResponse",
]

FundMovementType = Literal["deposit", "withdrawal"]


class UserFund(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    movement_type: FundMovementType
    amount: float
    balance_after: float
    timestamp: int
    transaction_version: int


class UserFundHistoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    funds: list[UserFund]
    total: int


class UserFundHistoryReader(BaseReader):
    async def get_by_addr(
        self, *, sub_addr: str, limit: int = 200, offset: int = 0
    ) -> UserFundHistoryResponse:
        response, _, _ = await self.get_request(
            model=UserFundHistoryResponse,
            url=f"{self.config.trading_http_url}/api/v1/account_fund_history",
            params={
                "account": sub_addr,
                "limit": str(limit),
                "offset": str(offset),
            },
        )
        return response
