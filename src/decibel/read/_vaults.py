from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, RootModel

from ._base import BaseReader

logger = logging.getLogger(__name__)

__all__ = [
    "UserOwnedVault",
    "UserOwnedVaultsResponse",
    "UserPerformanceOnVault",
    "Vault",
    "VaultDeposit",
    "VaultsReader",
    "VaultsResponse",
    "VaultType",
    "VaultWithdrawal",
]

VaultType = Literal["user", "protocol"]


class Vault(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    address: str
    name: str
    description: str | None
    manager: str
    status: str
    created_at: int
    tvl: float | None
    volume: float | None
    volume_30d: float | None
    all_time_pnl: float | None
    net_deposits: float | None
    all_time_return: float | None
    past_month_return: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    weekly_win_rate_12w: float | None
    profit_share: float | None
    pnl_90d: float | None
    manager_cash_pct: float | None
    average_leverage: float | None
    depositors: int | None
    perp_equity: float | None
    vault_type: VaultType | None
    social_links: list[str] | None


class VaultsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[Vault]
    total_count: int
    total_value_locked: float
    total_volume: float


class UserOwnedVault(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vault_address: str
    vault_name: str
    vault_share_symbol: str
    status: str
    age_days: int
    num_managers: int
    tvl: float | None
    apr: float | None
    manager_equity: float | None
    manager_stake: float | None


class UserOwnedVaultsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[UserOwnedVault]
    total_count: int


class VaultDeposit(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    amount_usdc: float
    shares_received: float
    timestamp_ms: int
    unlock_timestamp_ms: int | None


class VaultWithdrawal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    amount_usdc: float | None
    shares_redeemed: float
    timestamp_ms: int
    status: str


class UserPerformanceOnVault(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vault: Vault
    account_address: str
    total_deposited: float | None
    total_withdrawn: float | None
    current_num_shares: float | None
    current_value_of_shares: float | None
    share_price: float | None
    all_time_earned: float | None
    all_time_return: float | None
    volume: float | None
    weekly_win_rate_12w: float | None
    deposits: list[VaultDeposit] | None
    withdrawals: list[VaultWithdrawal] | None
    locked_amount: float | None
    unrealized_pnl: float | None


class _UserPerformancesOnVaultsList(RootModel[list[UserPerformanceOnVault]]):
    pass


class VaultsReader(BaseReader):
    async def get_vaults(
        self,
        *,
        vault_type: VaultType | None = None,
        limit: int | None = None,
        offset: int | None = None,
        address: str | None = None,
        search: str | None = None,
    ) -> VaultsResponse:
        params: dict[str, str] = {}
        if vault_type is not None:
            params["vault_type"] = vault_type
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if address is not None:
            params["vault_address"] = address
        if search is not None:
            params["search"] = search

        response, _, _ = await self.get_request(
            model=VaultsResponse,
            url=f"{self.config.trading_http_url}/api/v1/vaults",
            params=params if params else None,
        )
        return response

    async def get_user_owned_vaults(
        self,
        *,
        owner_addr: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> UserOwnedVaultsResponse:
        params: dict[str, str] = {"account": owner_addr}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        response, _, _ = await self.get_request(
            model=UserOwnedVaultsResponse,
            url=f"{self.config.trading_http_url}/api/v1/account_owned_vaults",
            params=params,
        )
        return response

    async def get_user_performances_on_vaults(
        self,
        *,
        owner_addr: str,
    ) -> list[UserPerformanceOnVault]:
        response, _, _ = await self.get_request(
            model=_UserPerformancesOnVaultsList,
            url=f"{self.config.trading_http_url}/api/v1/account_vault_performance",
            params={"account": owner_addr},
        )
        return response.root

    async def get_vault_share_price(self, *, vault_address: str) -> float:
        try:
            nav_bytes = await self.aptos.view(
                f"{self.config.deployment.package}::vault::get_vault_net_asset_value",
                [],
                [vault_address],
            )
            shares_bytes = await self.aptos.view(
                f"{self.config.deployment.package}::vault::get_vault_num_shares",
                [],
                [vault_address],
            )

            nav_result: list[Any] = json.loads(nav_bytes.decode("utf-8"))
            shares_result: list[Any] = json.loads(shares_bytes.decode("utf-8"))

            nav_value = int(nav_result[0])
            shares_value = int(shares_result[0])

            if shares_value == 0:
                return 1.0

            # Calculate share price: NAV / num_shares
            # Note: This may lose precision for very large numbers
            return float(nav_value) / float(shares_value)
        except Exception as e:
            logger.error("Failed to get vault share price for %s: %s", vault_address, e)
            return 1.0
