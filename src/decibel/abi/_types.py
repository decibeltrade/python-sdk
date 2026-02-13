from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ABIData",
    "ABIErrorEntry",
    "ABISummary",
    "MoveFunction",
    "MoveFunctionId",
]

MoveFunctionId = str


class MoveFunction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    visibility: str
    is_entry: bool
    is_view: bool
    generic_type_params: list[dict[str, object]]
    params: list[str]
    return_: list[str] = Field(alias="return")


class ABIErrorEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    module: str
    function: str
    error: str


class ABISummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_modules: int = Field(alias="totalModules")
    total_functions: int = Field(alias="totalFunctions")
    successful: int
    failed: int


class ABIData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    package_address: str = Field(alias="packageAddress")
    network: str
    fullnode_url: str = Field(alias="fullnodeUrl")
    fetched_at: str = Field(alias="fetchedAt")
    abis: dict[MoveFunctionId, MoveFunction]
    errors: list[ABIErrorEntry]
    summary: ABISummary
    modules: list[str]
