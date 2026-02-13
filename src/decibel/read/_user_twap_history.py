from __future__ import annotations

from pydantic import BaseModel

from ._base import BaseReader
from ._user_active_twaps import UserActiveTwap

__all__ = [
    "UserTwapHistoryReader",
    "UserTwapHistoryResponse",
]


class UserTwapHistoryResponse(BaseModel):
    items: list[UserActiveTwap]
    total_count: int


class UserTwapHistoryReader(BaseReader):
    async def get_by_addr(
        self,
        *,
        sub_addr: str,
        limit: int = 100,
        offset: int = 0,
    ) -> UserTwapHistoryResponse:
        response, _, _ = await self.get_request(
            model=UserTwapHistoryResponse,
            url=f"{self.config.trading_http_url}/api/v1/twap_history",
            params={"user": sub_addr, "limit": str(limit), "offset": str(offset)},
        )
        return response
