from __future__ import annotations

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "Delegation",
    "DelegationsReader",
]


class Delegation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    delegated_account: str
    permission_type: str
    expiration_time_s: float | None


class _DelegationsList(RootModel[list[Delegation]]):
    pass


class DelegationsReader(BaseReader):
    async def get_all(self, *, sub_addr: str) -> list[Delegation]:
        response, _, _ = await self.get_request(
            model=_DelegationsList,
            url=f"{self.config.trading_http_url}/api/v1/delegations",
            params={"subaccount": sub_addr},
        )
        return response.root
