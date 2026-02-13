from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# TODO: Put this in a separate folder and split up write module

__all__ = [
    "SubaccountCreatedEvent",
    "SubaccountActiveChangedEvent",
    "CreateSubaccountResponse",
    "RenameSubaccountArgs",
    "RenameSubaccount",
]


class SubaccountCreatedEvent(BaseModel):
    is_primary: bool
    owner: str
    subaccount: str


class SubaccountActiveChangedEvent(BaseModel):
    is_active: bool
    owner: str
    subaccount: str


class CreateSubaccountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    subaccount_address: str | None = Field(alias="subaccountAddress")


class RenameSubaccountArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    subaccount_address: str = Field(alias="subaccountAddress")
    new_name: str = Field(alias="newName")


class RenameSubaccount(BaseModel):
    subaccount_address: str
    new_name: str
