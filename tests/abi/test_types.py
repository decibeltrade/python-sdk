from __future__ import annotations

from decibel.abi import ABIData, ABIErrorEntry, ABISummary, MoveFunction


class TestMoveFunction:
    def test_parse_with_return_alias(self) -> None:
        data = {
            "name": "get_balance",
            "visibility": "public",
            "is_entry": False,
            "is_view": True,
            "generic_type_params": [],
            "params": ["address"],
            "return": ["u64"],
        }
        func = MoveFunction.model_validate(data)
        assert func.name == "get_balance"
        assert func.visibility == "public"
        assert func.is_entry is False
        assert func.is_view is True
        assert func.return_ == ["u64"]

    def test_parse_with_snake_case(self) -> None:
        data = {
            "name": "transfer",
            "visibility": "public",
            "is_entry": True,
            "is_view": False,
            "generic_type_params": [],
            "params": ["&signer", "address", "u64"],
            "return_": [],
        }
        func = MoveFunction.model_validate(data)
        assert func.is_entry is True
        assert func.return_ == []

    def test_dump_uses_camel_case(self) -> None:
        func = MoveFunction(
            name="test",
            visibility="public",
            is_entry=True,
            is_view=False,
            generic_type_params=[],
            params=[],
            return_=["bool"],
        )
        data = func.model_dump(by_alias=True)
        assert "return" in data
        assert data["return"] == ["bool"]


class TestABISummary:
    def test_parse_from_camel_case(self) -> None:
        data = {
            "totalModules": 7,
            "totalFunctions": 151,
            "successful": 151,
            "failed": 0,
        }
        summary = ABISummary.model_validate(data)
        assert summary.total_modules == 7
        assert summary.total_functions == 151
        assert summary.successful == 151
        assert summary.failed == 0


class TestABIErrorEntry:
    def test_parse(self) -> None:
        data = {
            "module": "public_apis",
            "function": "place_order",
            "error": "Function not found",
        }
        entry = ABIErrorEntry.model_validate(data)
        assert entry.module == "public_apis"
        assert entry.function == "place_order"
        assert entry.error == "Function not found"


class TestABIData:
    def test_parse_minimal(self) -> None:
        data = {
            "packageAddress": "0x123",
            "network": "testnet",
            "fullnodeUrl": "https://api.testnet.aptoslabs.com/v1",
            "fetchedAt": "2025-01-01T00:00:00Z",
            "abis": {},
            "errors": [],
            "summary": {
                "totalModules": 0,
                "totalFunctions": 0,
                "successful": 0,
                "failed": 0,
            },
            "modules": [],
        }
        abi_data = ABIData.model_validate(data)
        assert abi_data.package_address == "0x123"
        assert abi_data.network == "testnet"
        assert abi_data.modules == []

    def test_parse_with_abis(self) -> None:
        data = {
            "packageAddress": "0x123",
            "network": "testnet",
            "fullnodeUrl": "https://api.testnet.aptoslabs.com/v1",
            "fetchedAt": "2025-01-01T00:00:00Z",
            "abis": {
                "0x123::module::func": {
                    "name": "func",
                    "visibility": "public",
                    "is_entry": True,
                    "is_view": False,
                    "generic_type_params": [],
                    "params": [],
                    "return": [],
                }
            },
            "errors": [],
            "summary": {
                "totalModules": 1,
                "totalFunctions": 1,
                "successful": 1,
                "failed": 0,
            },
            "modules": ["module"],
        }
        abi_data = ABIData.model_validate(data)
        assert len(abi_data.abis) == 1
        assert "0x123::module::func" in abi_data.abis
        assert abi_data.abis["0x123::module::func"].name == "func"
