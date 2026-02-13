from __future__ import annotations

import importlib.resources
import json
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING

from decibel.abi._types import ABIData, MoveFunction, MoveFunctionId

if TYPE_CHECKING:
    from importlib.abc import Traversable

__all__ = [
    "AbiRegistry",
    "get_abi_data",
    "get_default_abi_data",
]

CHAIN_ID_NETNA = 208
CHAIN_ID_TESTNET = 2


@lru_cache(maxsize=4)
def _load_abi_json(filename: str) -> ABIData:
    json_dir: Traversable = importlib.resources.files("decibel.abi") / "json"
    json_file = json_dir / filename
    with json_file.open("r") as f:
        data = json.load(f)
    return ABIData.model_validate(data)


def get_abi_data(chain_id: int | None) -> ABIData:
    if chain_id == CHAIN_ID_NETNA:
        return _load_abi_json("netna.json")
    elif chain_id == CHAIN_ID_TESTNET:
        return _load_abi_json("testnet.json")
    else:
        warnings.warn(
            f"Unknown chain_id {chain_id}, falling back to NETNA ABIs",
            stacklevel=2,
        )
        return _load_abi_json("netna.json")


def get_default_abi_data() -> ABIData:
    return _load_abi_json("netna.json")


class AbiRegistry:
    def __init__(self, chain_id: int | None = None) -> None:
        self._chain_id = chain_id
        self._abi_data: ABIData | None = None

    @property
    def abi_data(self) -> ABIData:
        if self._abi_data is None:
            if self._chain_id is None:
                self._abi_data = get_default_abi_data()
            else:
                self._abi_data = get_abi_data(self._chain_id)
        return self._abi_data

    @property
    def package_address(self) -> str:
        return self.abi_data.package_address

    @property
    def modules(self) -> list[str]:
        return self.abi_data.modules

    def get_function(self, function_id: MoveFunctionId) -> MoveFunction | None:
        return self.abi_data.abis.get(function_id)

    def get_all_functions(self) -> dict[MoveFunctionId, MoveFunction]:
        return self.abi_data.abis

    def get_entry_functions(self) -> dict[MoveFunctionId, MoveFunction]:
        return {fid: func for fid, func in self.abi_data.abis.items() if func.is_entry}

    def get_view_functions(self) -> dict[MoveFunctionId, MoveFunction]:
        return {fid: func for fid, func in self.abi_data.abis.items() if func.is_view}

    def get_module_functions(self, module_name: str) -> dict[MoveFunctionId, MoveFunction]:
        pattern = f"::{module_name}::"
        return {fid: func for fid, func in self.abi_data.abis.items() if pattern in fid}

    def has_function(self, function_id: MoveFunctionId) -> bool:
        return function_id in self.abi_data.abis
