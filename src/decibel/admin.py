from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import httpx
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
        result = await self._aptos.view(
            "0x1::primary_fungible_store::balance",
            ["0x1::fungible_asset::Metadata"],
            [addr_str, self._config.deployment.usdc],
        )
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

        def make_request(client: httpx.Client) -> int:
            response = client.post(
                f"{self._config.fullnode_url}/view",
                json={
                    "function": "0x1::primary_fungible_store::balance",
                    "type_arguments": ["0x1::fungible_asset::Metadata"],
                    "arguments": [addr_str, self._config.deployment.usdc],
                },
            )
            data = cast("list[Any]", response.json())
            return int(data[0])

        if self._http_client is not None:
            return make_request(self._http_client)
        with httpx.Client() as client:
            return make_request(client)
