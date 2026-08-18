from __future__ import annotations

import warnings

import pytest

from decibel._constants import MAINNET_CONFIG, TESTNET_CONFIG, DecibelConfig
from decibel.abi import AbiRegistry, get_abi_data, get_default_abi_data


class TestGetAbiData:
    def test_testnet_chain_id(self) -> None:
        data = get_abi_data(2)
        assert data.network == "testnet"
        assert "testnet" in data.fullnode_url

    def test_unknown_chain_id_falls_back_with_warning(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            data = get_abi_data(999)
            assert len(w) == 1
            assert "Unknown chain_id" in str(w[0].message)
            assert "testnet" in data.fullnode_url


class TestGetDefaultAbiData:
    def test_returns_testnet(self) -> None:
        data = get_default_abi_data()
        assert "testnet" in data.fullnode_url


class TestAbiRegistry:
    def test_init_with_default(self) -> None:
        registry = AbiRegistry()
        assert registry.package_address is not None
        assert len(registry.modules) == 18
        assert "dex_accounts_spot_entry" in registry.modules
        assert "spot_engine" in registry.modules

    def test_init_with_testnet_chain_id(self) -> None:
        registry = AbiRegistry(chain_id=2)
        assert "testnet" in registry.abi_data.fullnode_url

    def test_get_all_functions(self) -> None:
        registry = AbiRegistry()
        funcs = registry.get_all_functions()
        assert len(funcs) > 0

    def test_get_entry_functions(self) -> None:
        registry = AbiRegistry()
        entry_funcs = registry.get_entry_functions()
        assert len(entry_funcs) > 0
        for func in entry_funcs.values():
            assert func.is_entry is True

    def test_get_view_functions(self) -> None:
        registry = AbiRegistry()
        view_funcs = registry.get_view_functions()
        assert len(view_funcs) > 0
        for func in view_funcs.values():
            assert func.is_view is True

    def test_get_module_functions(self) -> None:
        registry = AbiRegistry()
        admin_funcs = registry.get_module_functions("admin_apis")
        assert len(admin_funcs) > 0
        for fid in admin_funcs:
            assert "::admin_apis::" in fid

    def test_get_function_exists(self) -> None:
        registry = AbiRegistry()
        package = registry.package_address
        func = registry.get_function(f"{package}::dex_accounts_entry::place_order_to_subaccount")
        assert func is not None
        assert func.name == "place_order_to_subaccount"

    def test_get_function_not_found(self) -> None:
        registry = AbiRegistry()
        func = registry.get_function("0x123::nonexistent::func")
        assert func is None

    def test_has_function(self) -> None:
        registry = AbiRegistry()
        package = registry.package_address
        assert (
            registry.has_function(f"{package}::dex_accounts_entry::place_order_to_subaccount")
            is True
        )
        assert registry.has_function("0x123::nonexistent::func") is False

    def test_modules_list(self) -> None:
        registry = AbiRegistry()
        assert "admin_apis" in registry.modules
        assert "public_apis" in registry.modules
        assert "dex_accounts" in registry.modules


@pytest.mark.parametrize("config", [TESTNET_CONFIG, MAINNET_CONFIG], ids=["testnet", "mainnet"])
class TestBundledWriteCoverage:
    """Guards that the generator keeps covering the modules the write path calls into.

    `build_tx` can now fetch a missing ABI from the fullnode, so a gap here is a slow path rather
    than a hard failure — but it is still a gap, and one an extra round trip per module pays for.
    """

    def test_campaign_package_matches_deployment(self, config: DecibelConfig) -> None:
        registry = AbiRegistry(chain_id=config.chain_id)
        assert registry.campaign_package_address == config.deployment.campaign_package

    @pytest.mark.parametrize(
        "function",
        [
            "campaign_manager::claim_by_id",
            "funded_first_trade::lock",
            "funded_first_trade::lock_from_subaccount",
            "funded_first_trade::open_trial",
            "funded_first_trade::settle_trial",
            "funded_first_trade::unlock",
        ],
    )
    def test_campaign_function_is_bundled(self, config: DecibelConfig, function: str) -> None:
        registry = AbiRegistry(chain_id=config.chain_id)
        assert registry.has_function(f"{config.deployment.campaign_package}::{function}")

    @pytest.mark.parametrize(
        "function",
        [
            "dex_accounts_entry::place_order_to_subaccount",
            "dex_accounts_entry::withdraw_from_cross_collateral",
            "dex_accounts_spot_entry::place_spot_order_to_subaccount",
            "dex_accounts_spot_entry::cancel_spot_order_to_subaccount",
            "spot_admin_apis::register_market",
        ],
    )
    def test_package_function_is_bundled(self, config: DecibelConfig, function: str) -> None:
        registry = AbiRegistry(chain_id=config.chain_id)
        assert registry.has_function(f"{config.deployment.package}::{function}")
