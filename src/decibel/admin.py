from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from aptos_sdk.account_address import AccountAddress

from ._base import BaseSDK, BaseSDKSync
from ._transaction_builder import InputEntryFunctionData
from ._utils import get_market_addr

if TYPE_CHECKING:
    from aptos_sdk.account import Account

    from ._base import BaseSDKOptions, BaseSDKOptionsSync
    from ._constants import DecibelConfig

__all__ = [
    "DecibelAdminDex",
    "DecibelAdminDexSync",
    "DecibelSpotAdminDex",
    "DecibelSpotAdminDexSync",
]


class DecibelAdminDex(BaseSDK):
    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptions | None = None,
    ) -> None:
        super().__init__(config, account, opts)

    async def initialize(
        self,
        collateral_token_addr: str,
        backstop_liquidator_addr: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::initialize",
                type_arguments=[],
                function_arguments=[
                    collateral_token_addr,
                    backstop_liquidator_addr,
                ],
            )
        )

    def get_protocol_vault_address(self) -> AccountAddress:
        package_addr = AccountAddress.from_str(self._config.deployment.package)
        vault_config_addr = AccountAddress.for_named_object(package_addr, b"GlobalVaultConfig")
        return AccountAddress.for_named_object(vault_config_addr, b"Decibel Protocol Vault")

    async def initialize_protocol_vault(
        self,
        collateral_token_addr: str,
        initial_funding: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::create_and_fund_vault",
                type_arguments=[],
                function_arguments=[
                    self.get_primary_subaccount_address(self._account.address()),
                    collateral_token_addr,
                    "Decibel Protocol Vault",
                    "(description)",
                    [],
                    "DPV",
                    "",
                    "",
                    0,  # fee_bps
                    0,  # fee_interval
                    3 * 24 * 60 * 60,  # contribution_lockup_duration_s
                    initial_funding,
                    True,  # accepts_contributions
                    False,  # delegate_to_creator
                ],
            )
        )

    async def delegate_protocol_vault_trading_to(
        self,
        vault_address: str,
        account_to_delegate_to: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::delegate_dex_actions_to",
                type_arguments=[],
                function_arguments=[vault_address, account_to_delegate_to, None],
            )
        )

    async def update_vault_use_global_redemption_slippage_adjustment(
        self,
        vault_address: str,
        use_global_redemption_slippage_adjustment: bool,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::update_vault_use_global_redemption_slippage_adjustment",
                type_arguments=[],
                function_arguments=[vault_address, use_global_redemption_slippage_adjustment],
            )
        )

    async def authorize_oracle_and_mark_update(
        self,
        internal_oracle_updater: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_oracle_and_mark_update_permission",
                type_arguments=[],
                function_arguments=[internal_oracle_updater],
            )
        )

    async def add_access_control_admin(
        self,
        delegated_admin: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_access_control_admin",
                type_arguments=[],
                function_arguments=[delegated_admin],
            )
        )

    async def add_market_list_admin(
        self,
        delegated_admin: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_market_list_admin",
                type_arguments=[],
                function_arguments=[delegated_admin],
            )
        )

    async def add_market_risk_governor(
        self,
        delegated_admin: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_market_risk_governor",
                type_arguments=[],
                function_arguments=[delegated_admin],
            )
        )

    async def register_market_with_internal_oracle(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        taker_in_next_block: bool = True,
        initial_oracle_price: int = 1,
        max_staleness_secs: int = 60,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_internal_oracle",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    initial_oracle_price,
                    max_staleness_secs,
                ],
            )
        )

    async def register_market_with_pyth_oracle(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        pyth_identifier_bytes: list[int],
        pyth_max_staleness_secs: int,
        pyth_confidence_interval_threshold: int,
        pyth_decimals: int,
        taker_in_next_block: bool = True,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_pyth_oracle",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    pyth_identifier_bytes,
                    pyth_max_staleness_secs,
                    pyth_confidence_interval_threshold,
                    pyth_decimals,
                ],
            )
        )

    async def register_market_with_composite_oracle_primary_pyth(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        pyth_identifier_bytes: list[int],
        pyth_max_staleness_secs: int,
        pyth_confidence_interval_threshold: int,
        pyth_decimals: int,
        internal_initial_price: int,
        internal_max_staleness_secs: int,
        oracles_deviation_bps: int,
        consecutive_deviation_count: int,
        taker_in_next_block: bool = True,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_composite_oracle_primary_pyth",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    pyth_identifier_bytes,
                    pyth_max_staleness_secs,
                    pyth_confidence_interval_threshold,
                    pyth_decimals,
                    internal_initial_price,
                    internal_max_staleness_secs,
                    oracles_deviation_bps,
                    consecutive_deviation_count,
                ],
            )
        )

    async def register_market_with_composite_oracle_primary_chainlink(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        rescale_decimals: int,
        chainlink_feed_id_bytes: list[int],
        chainlink_max_staleness_secs: int,
        internal_max_staleness_secs: int,
        internal_initial_price: int,
        oracles_deviation_bps: int,
        consecutive_deviation_count: int,
        taker_in_next_block: bool = True,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_composite_oracle_primary_chainlink",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    chainlink_feed_id_bytes,
                    chainlink_max_staleness_secs,
                    rescale_decimals,
                    internal_initial_price,
                    internal_max_staleness_secs,
                    oracles_deviation_bps,
                    consecutive_deviation_count,
                ],
            )
        )

    async def update_internal_oracle_price(
        self,
        market_name: str,
        oracle_price: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::update_mark_for_internal_oracle",
                type_arguments=[],
                function_arguments=[market_addr, oracle_price, [], [], True],
            )
        )

    async def update_pyth_oracle_price(
        self,
        market_name: str,
        vaa: list[int],
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::update_mark_for_pyth_oracle",
                type_arguments=[],
                function_arguments=[market_addr, vaa, [], [], True],
            )
        )

    async def set_market_adl_trigger_threshold(
        self,
        market_name: str,
        threshold: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::set_market_adl_trigger_threshold",
                type_arguments=[],
                function_arguments=[market_addr, threshold],
            )
        )

    async def update_price_to_pyth_only(
        self,
        vaas: list[list[int]],
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::pyth::update_price_feeds_with_funder",
                type_arguments=[],
                function_arguments=[vaas],
            )
        )

    async def update_price_to_chainlink_only(
        self,
        signed_report: list[int],
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::chainlink_state::verify_and_store_single_price",
                type_arguments=[],
                function_arguments=[signed_report],
            )
        )

    async def mint_usdc(
        self,
        to_addr: str | AccountAddress,
        amount: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        addr = str(to_addr) if isinstance(to_addr, AccountAddress) else to_addr
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::usdc::mint",
                type_arguments=[],
                function_arguments=[addr, amount],
            )
        )

    async def set_public_minting(
        self,
        allow: bool,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::usdc::set_public_minting",
                type_arguments=[],
                function_arguments=[allow],
            )
        )

    async def usdc_balance(
        self,
        addr: str | AccountAddress,
    ) -> int:
        addr_str = str(addr) if isinstance(addr, AccountAddress) else addr
        # RestClient.view returns the raw response body, so it has to be decoded before
        # indexing — indexing the bytes directly would yield a byte value, not the balance.
        result_bytes = await self._aptos.view(
            "0x1::primary_fungible_store::balance",
            ["0x1::fungible_asset::Metadata"],
            [addr_str, self._config.deployment.usdc],
        )
        result = cast("list[Any]", json.loads(result_bytes.decode("utf-8")))
        return int(result[0])


class DecibelAdminDexSync(BaseSDKSync):
    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptionsSync | None = None,
    ) -> None:
        super().__init__(config, account, opts)

    def initialize(
        self,
        collateral_token_addr: str,
        backstop_liquidator_addr: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::initialize",
                type_arguments=[],
                function_arguments=[
                    collateral_token_addr,
                    backstop_liquidator_addr,
                ],
            )
        )

    def get_protocol_vault_address(self) -> AccountAddress:
        package_addr = AccountAddress.from_str(self._config.deployment.package)
        vault_config_addr = AccountAddress.for_named_object(package_addr, b"GlobalVaultConfig")
        return AccountAddress.for_named_object(vault_config_addr, b"Decibel Protocol Vault")

    def initialize_protocol_vault(
        self,
        collateral_token_addr: str,
        initial_funding: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_api::create_and_fund_vault",
                type_arguments=[],
                function_arguments=[
                    self.get_primary_subaccount_address(self._account.address()),
                    collateral_token_addr,
                    "Decibel Protocol Vault",
                    "(description)",
                    [],
                    "DPV",
                    "",
                    "",
                    0,  # fee_bps
                    0,  # fee_interval
                    3 * 24 * 60 * 60,  # contribution_lockup_duration_s
                    initial_funding,
                    True,  # accepts_contributions
                    False,  # delegate_to_creator
                ],
            )
        )

    def delegate_protocol_vault_trading_to(
        self,
        vault_address: str,
        account_to_delegate_to: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::delegate_dex_actions_to",
                type_arguments=[],
                function_arguments=[vault_address, account_to_delegate_to, None],
            )
        )

    def update_vault_use_global_redemption_slippage_adjustment(
        self,
        vault_address: str,
        use_global_redemption_slippage_adjustment: bool,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::vault_admin_api::update_vault_use_global_redemption_slippage_adjustment",
                type_arguments=[],
                function_arguments=[vault_address, use_global_redemption_slippage_adjustment],
            )
        )

    def authorize_oracle_and_mark_update(
        self,
        internal_oracle_updater: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_oracle_and_mark_update_permission",
                type_arguments=[],
                function_arguments=[internal_oracle_updater],
            )
        )

    def add_access_control_admin(
        self,
        delegated_admin: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_access_control_admin",
                type_arguments=[],
                function_arguments=[delegated_admin],
            )
        )

    def add_market_list_admin(
        self,
        delegated_admin: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_market_list_admin",
                type_arguments=[],
                function_arguments=[delegated_admin],
            )
        )

    def add_market_risk_governor(
        self,
        delegated_admin: str,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::add_market_risk_governor",
                type_arguments=[],
                function_arguments=[delegated_admin],
            )
        )

    def register_market_with_internal_oracle(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        taker_in_next_block: bool = True,
        initial_oracle_price: int = 1,
        max_staleness_secs: int = 60,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_internal_oracle",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    initial_oracle_price,
                    max_staleness_secs,
                ],
            )
        )

    def register_market_with_pyth_oracle(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        pyth_identifier_bytes: list[int],
        pyth_max_staleness_secs: int,
        pyth_confidence_interval_threshold: int,
        pyth_decimals: int,
        taker_in_next_block: bool = True,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_pyth_oracle",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    pyth_identifier_bytes,
                    pyth_max_staleness_secs,
                    pyth_confidence_interval_threshold,
                    pyth_decimals,
                ],
            )
        )

    def register_market_with_composite_oracle_primary_pyth(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        pyth_identifier_bytes: list[int],
        pyth_max_staleness_secs: int,
        pyth_confidence_interval_threshold: int,
        pyth_decimals: int,
        internal_initial_price: int,
        internal_max_staleness_secs: int,
        oracles_deviation_bps: int,
        consecutive_deviation_count: int,
        taker_in_next_block: bool = True,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_composite_oracle_primary_pyth",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    pyth_identifier_bytes,
                    pyth_max_staleness_secs,
                    pyth_confidence_interval_threshold,
                    pyth_decimals,
                    internal_initial_price,
                    internal_max_staleness_secs,
                    oracles_deviation_bps,
                    consecutive_deviation_count,
                ],
            )
        )

    def register_market_with_composite_oracle_primary_chainlink(
        self,
        name: str,
        sz_decimals: int,
        min_size: int,
        lot_size: int,
        ticker_size: int,
        max_open_interest: int,
        max_leverage: int,
        margin_call_fee_pct: int,
        rescale_decimals: int,
        chainlink_feed_id_bytes: list[int],
        chainlink_max_staleness_secs: int,
        internal_max_staleness_secs: int,
        internal_initial_price: int,
        oracles_deviation_bps: int,
        consecutive_deviation_count: int,
        taker_in_next_block: bool = True,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::register_market_with_composite_oracle_primary_chainlink",
                type_arguments=[],
                function_arguments=[
                    name,
                    sz_decimals,
                    min_size,
                    lot_size,
                    ticker_size,
                    max_open_interest,
                    max_leverage,
                    margin_call_fee_pct,
                    taker_in_next_block,
                    chainlink_feed_id_bytes,
                    chainlink_max_staleness_secs,
                    rescale_decimals,
                    internal_initial_price,
                    internal_max_staleness_secs,
                    oracles_deviation_bps,
                    consecutive_deviation_count,
                ],
            )
        )

    def update_internal_oracle_price(
        self,
        market_name: str,
        oracle_price: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::update_mark_for_internal_oracle",
                type_arguments=[],
                function_arguments=[market_addr, oracle_price, [], [], True],
            )
        )

    def update_pyth_oracle_price(
        self,
        market_name: str,
        vaa: list[int],
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::update_mark_for_pyth_oracle",
                type_arguments=[],
                function_arguments=[market_addr, vaa, [], [], True],
            )
        )

    def set_market_adl_trigger_threshold(
        self,
        market_name: str,
        threshold: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        market_addr = get_market_addr(market_name, self._config.deployment.perp_engine_global)
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::admin_apis::set_market_adl_trigger_threshold",
                type_arguments=[],
                function_arguments=[market_addr, threshold],
            )
        )

    def update_price_to_pyth_only(
        self,
        vaas: list[list[int]],
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::pyth::update_price_feeds_with_funder",
                type_arguments=[],
                function_arguments=[vaas],
            )
        )

    def update_price_to_chainlink_only(
        self,
        signed_report: list[int],
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::chainlink_state::verify_and_store_single_price",
                type_arguments=[],
                function_arguments=[signed_report],
            )
        )

    def mint_usdc(
        self,
        to_addr: str | AccountAddress,
        amount: int,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        addr = str(to_addr) if isinstance(to_addr, AccountAddress) else to_addr
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::usdc::mint",
                type_arguments=[],
                function_arguments=[addr, amount],
            )
        )

    def set_public_minting(
        self,
        allow: bool,
    ) -> dict[str, Any]:
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::usdc::set_public_minting",
                type_arguments=[],
                function_arguments=[allow],
            )
        )

    def usdc_balance(
        self,
        addr: str | AccountAddress,
    ) -> int:
        addr_str = str(addr) if isinstance(addr, AccountAddress) else addr

        response = self._http_client.post(
            f"{self._config.fullnode_url}/view",
            json={
                "function": "0x1::primary_fungible_store::balance",
                "type_arguments": ["0x1::fungible_asset::Metadata"],
                "arguments": [addr_str, self._config.deployment.usdc],
            },
        )
        response.raise_for_status()
        data = cast("list[Any]", response.json())
        return int(data[0])


class DecibelSpotAdminDex(BaseSDK):
    """Admin operations for the Spot DEX (``spot_admin_apis``).

    Separate from perp's :class:`DecibelAdminDex`; the entries require the deployer / owner
    of the ``@decibel_dex`` code object.
    """

    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptions | None = None,
    ) -> None:
        super().__init__(config, account, opts)

    async def set_usdc_quote_metadata(self, usdc_metadata_addr: str) -> dict[str, Any]:
        """Bind the canonical USDC quote metadata.

        Required before :meth:`register_market`, which otherwise aborts with
        ``EUSDC_QUOTE_NOT_BOUND``. Idempotent.
        """
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::spot_admin_apis::set_usdc_quote_metadata",
                type_arguments=[],
                function_arguments=[usdc_metadata_addr],
            )
        )

    async def register_market(
        self,
        name: str,
        base_asset: str,
        quote_asset: str,
        tick_size: int,
        lot_size: int,
        min_size: int,
        async_matching_enabled: bool,
        min_price: int,
        max_price: int,
    ) -> dict[str, Any]:
        """Register a base/quote spot market.

        ``tick_size`` / ``min_price`` / ``max_price`` are raw quote units per whole base unit;
        ``lot_size`` / ``min_size`` are raw base units. On-chain requires
        ``(tick_size * lot_size) % 10^base_decimals == 0`` and ``min_size % lot_size == 0``.
        """
        pkg = self._config.deployment.package
        return await self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::spot_admin_apis::register_market",
                type_arguments=[],
                function_arguments=[
                    name,
                    base_asset,
                    quote_asset,
                    str(tick_size),
                    str(lot_size),
                    str(min_size),
                    async_matching_enabled,
                    str(min_price),
                    str(max_price),
                ],
            )
        )

    async def list_market_addresses(self) -> list[str]:
        """Addresses of all registered spot markets."""
        pkg = self._config.deployment.package
        result_bytes = await self._aptos.view(
            f"{pkg}::spot_engine::list_markets",
            [],
            [],
        )
        result = cast("list[Any]", json.loads(result_bytes.decode("utf-8")))
        return [str(addr) for addr in cast("list[Any]", result[0])]


class DecibelSpotAdminDexSync(BaseSDKSync):
    """Sync mirror of :class:`DecibelSpotAdminDex`."""

    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptionsSync | None = None,
    ) -> None:
        super().__init__(config, account, opts)

    def set_usdc_quote_metadata(self, usdc_metadata_addr: str) -> dict[str, Any]:
        """Bind the canonical USDC quote metadata.

        Required before :meth:`register_market`, which otherwise aborts with
        ``EUSDC_QUOTE_NOT_BOUND``. Idempotent.
        """
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::spot_admin_apis::set_usdc_quote_metadata",
                type_arguments=[],
                function_arguments=[usdc_metadata_addr],
            )
        )

    def register_market(
        self,
        name: str,
        base_asset: str,
        quote_asset: str,
        tick_size: int,
        lot_size: int,
        min_size: int,
        async_matching_enabled: bool,
        min_price: int,
        max_price: int,
    ) -> dict[str, Any]:
        """Register a base/quote spot market.

        ``tick_size`` / ``min_price`` / ``max_price`` are raw quote units per whole base unit;
        ``lot_size`` / ``min_size`` are raw base units. On-chain requires
        ``(tick_size * lot_size) % 10^base_decimals == 0`` and ``min_size % lot_size == 0``.
        """
        pkg = self._config.deployment.package
        return self._send_tx(
            InputEntryFunctionData(
                function=f"{pkg}::spot_admin_apis::register_market",
                type_arguments=[],
                function_arguments=[
                    name,
                    base_asset,
                    quote_asset,
                    str(tick_size),
                    str(lot_size),
                    str(min_size),
                    async_matching_enabled,
                    str(min_price),
                    str(max_price),
                ],
            )
        )

    def list_market_addresses(self) -> list[str]:
        """Addresses of all registered spot markets."""
        pkg = self._config.deployment.package
        response = self._http_client.post(
            f"{self._config.fullnode_url}/view",
            json={
                "function": f"{pkg}::spot_engine::list_markets",
                "type_arguments": [],
                "arguments": [],
            },
        )
        response.raise_for_status()
        data = cast("list[Any]", response.json())
        return [str(addr) for addr in cast("list[Any]", data[0])]
