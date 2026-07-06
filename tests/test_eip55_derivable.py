"""Tests for EIP-55 checksums and derivable-account address derivation."""

from __future__ import annotations

import re

import pytest

from decibel._derivable_account import derive_aptos_from_eth, derive_aptos_from_solana
from decibel._eip55 import to_checksum_address

_APTOS_ADDR_RE = re.compile(r"^0x[a-f0-9]{64}$")

# Well-known EIP-55 checksummed addresses (from the EIP-55 spec / ethers).
_EIP55_VECTORS = [
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
    "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
]


class TestToChecksumAddress:
    @pytest.mark.parametrize("checksummed", _EIP55_VECTORS)
    def test_checksums_match_from_lowercase(self, checksummed: str) -> None:
        lower = checksummed.lower()
        assert to_checksum_address(lower) == checksummed

    def test_idempotent_on_checksummed(self) -> None:
        addr = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        assert to_checksum_address(addr) == addr

    @pytest.mark.parametrize("bad", ["not-an-address", "0x123", "d8da6bf2", "0x" + "z" * 40])
    def test_raises_on_invalid(self, bad: str) -> None:
        with pytest.raises(ValueError, match="Invalid Ethereum address"):
            to_checksum_address(bad)


class TestDeriveAptosFromEth:
    def test_produces_aptos_address(self) -> None:
        result = derive_aptos_from_eth("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        assert _APTOS_ADDR_RE.match(result)
        assert len(result) == 66

    def test_is_deterministic(self) -> None:
        addr = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        assert derive_aptos_from_eth(addr) == derive_aptos_from_eth(addr)

    def test_normalizes_case(self) -> None:
        lower = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
        mixed = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
        assert derive_aptos_from_eth(lower) == derive_aptos_from_eth(mixed)

    def test_different_inputs_differ(self) -> None:
        a = derive_aptos_from_eth("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        b = derive_aptos_from_eth("0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B")
        assert a != b

    def test_raises_on_invalid(self) -> None:
        with pytest.raises(ValueError):
            derive_aptos_from_eth("not-an-address")


class TestDeriveAptosFromSolana:
    def test_produces_aptos_address(self) -> None:
        result = derive_aptos_from_solana("11111111111111111111111111111111")
        assert _APTOS_ADDR_RE.match(result)
        assert len(result) == 66

    def test_is_deterministic(self) -> None:
        addr = "11111111111111111111111111111111"
        assert derive_aptos_from_solana(addr) == derive_aptos_from_solana(addr)

    def test_different_inputs_differ(self) -> None:
        a = derive_aptos_from_solana("11111111111111111111111111111111")
        b = derive_aptos_from_solana("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        assert a != b


def test_derive_rejects_malformed_auth_function() -> None:
    from decibel._derivable_account import _derive_aptos_address  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="Invalid auth function"):
        _derive_aptos_address("0x1::only_two_parts", "identity")
