from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PerpPosition",
    "CrossedPosition",
    "AssetType",
    "Precision",
    "BalanceTable",
    "Store",
    "StoreExtendRef",
    "CollateralBalanceSheet",
    "LiquidationConfigV1",
    "GlobalAccountsStateV1",
    "GlobalAccountsState",
    "CreateVaultArgs",
    "ActivateVaultArgs",
    "DepositToVaultArgs",
    "WithdrawFromVaultArgs",
]


class PerpPosition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    size: float
    sz_decimals: int
    entry_px: float
    max_leverage: float
    is_long: bool
    token_type: str


class CrossedPosition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    positions: list[PerpPosition]


class AssetType(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    inner: str


class Precision(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    decimals: int
    multiplier: str


class BalanceTable(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    handle: str


class Store(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    inner: str


class StoreExtendRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    self_: str = Field(alias="self")


class CollateralBalanceSheet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_type: AssetType
    asset_precision: Precision
    balance_precision: Precision
    balance_table: BalanceTable
    store: Store
    store_extend_ref: StoreExtendRef


class LiquidationConfigV1(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    variant: Literal["V1"] = Field(alias="__variant__")
    backstop_liquidator: str
    backstop_margin_maintenance_divisor: str
    backstop_margin_maintenance_multiplier: str
    maintenance_margin_leverage_divisor: str
    maintenance_margin_leverage_multiplier: str


class GlobalAccountsStateV1(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    variant: str = Field(alias="__variant__")
    collateral: CollateralBalanceSheet
    liquidation_config: LiquidationConfigV1


GlobalAccountsState = GlobalAccountsStateV1


class CreateVaultArgs(TypedDict):
    vault_name: str
    vault_description: str
    vault_social_links: list[str]
    vault_share_symbol: str
    fee_bps: int
    fee_interval_s: int
    contribution_lockup_duration_s: int
    initial_funding: float
    accepts_contributions: bool
    delegate_to_creator: bool
    subaccount_addr: NotRequired[str | None]
    contribution_asset_type: NotRequired[str]
    vault_share_icon_uri: NotRequired[str]
    vault_share_project_uri: NotRequired[str]


class ActivateVaultArgs(TypedDict):
    vault_address: str
    additional_funding: NotRequired[float]


class DepositToVaultArgs(TypedDict):
    vault_address: str
    amount: float


class WithdrawFromVaultArgs(TypedDict):
    vault_address: str
    shares: float
