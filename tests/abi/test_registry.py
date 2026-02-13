from __future__ import annotations

import warnings

from decibel.abi import AbiRegistry, get_abi_data, get_default_abi_data


class TestGetAbiData:
    def test_netna_chain_id(self) -> None:
        data = get_abi_data(208)
        assert data.network == "custom"
        assert "netna" in data.fullnode_url

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
            assert "netna" in data.fullnode_url


class TestGetDefaultAbiData:
    def test_returns_netna(self) -> None:
        data = get_default_abi_data()
        assert "netna" in data.fullnode_url


class TestAbiRegistry:
    def test_init_with_default(self) -> None:
        registry = AbiRegistry()
        assert registry.package_address is not None
        assert len(registry.modules) == 9

    def test_init_with_netna_chain_id(self) -> None:
        registry = AbiRegistry(chain_id=208)
        assert "netna" in registry.abi_data.fullnode_url

    def test_init_with_testnet_chain_id(self) -> None:
        registry = AbiRegistry(chain_id=2)
        assert "testnet" in registry.abi_data.fullnode_url

    def test_get_all_functions(self) -> None:
        registry = AbiRegistry()
        funcs = registry.get_all_functions()
        assert len(funcs) == 172

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
