from __future__ import annotations

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

__all__ = [
    "UserSubaccount",
    "UserSubaccountsReader",
]


class UserSubaccount(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    subaccount_address: str
    primary_account_address: str
    is_primary: bool
    is_active: bool | None = None
    custom_label: str | None


class _UserSubaccountsList(RootModel[list[UserSubaccount]]):
    pass


class UserSubaccountsReader(BaseReader):
    async def get_by_addr(self, *, owner_addr: str) -> list[UserSubaccount]:
        # TODO: Endpoint may change to /user_subaccounts
        response, _, _ = await self.get_request(
            model=_UserSubaccountsList,
            url=f"{self.config.trading_http_url}/api/v1/subaccounts",
            params={"owner": owner_addr},
        )
        return response.root
