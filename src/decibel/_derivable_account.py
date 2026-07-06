"""Derive Aptos account addresses from EVM/Solana wallets (scheme byte 0x05)."""

from __future__ import annotations

import hashlib

from aptos_sdk.account_address import AccountAddress
from aptos_sdk.bcs import Serializer

from ._eip55 import to_checksum_address

__all__ = [
    "derive_aptos_from_eth",
    "derive_aptos_from_solana",
]

_DOMAIN = "app.decibel.trade"
_ETH_AUTH_FN = "0x1::ethereum_derivable_account::authenticate"
_SOL_AUTH_FN = "0x1::solana_derivable_account::authenticate"

# Derivable abstraction authentication-key scheme byte.
_DERIVABLE_ABSTRACTION_SCHEME = 0x05


def _derive_aptos_address(auth_fn: str, identity: str) -> str:
    parts = auth_fn.split("::")
    if len(parts) != 3:
        raise ValueError(f"Invalid auth function: {auth_fn}")

    # Serialize the FunctionInfo (module address, module name, function name).
    s1 = Serializer()
    AccountAddress.from_str(parts[0]).serialize(s1)
    s1.str(parts[1])
    s1.str(parts[2])

    # Serialize the DerivableAbstractPublicKey (identity, domain), then wrap as bytes.
    apk = Serializer()
    apk.str(identity)
    apk.str(_DOMAIN)

    s2 = Serializer()
    s2.to_bytes(apk.output())

    data = hashlib.sha3_256(
        s1.output() + s2.output() + bytes([_DERIVABLE_ABSTRACTION_SCHEME])
    ).digest()
    return str(AccountAddress(data))


def derive_aptos_from_eth(eth_address: str) -> str:
    """Derive an Aptos address from an Ethereum wallet address.

    The ETH address is checksummed via EIP-55 before derivation.
    """
    return _derive_aptos_address(_ETH_AUTH_FN, to_checksum_address(eth_address))


def derive_aptos_from_solana(sol_address: str) -> str:
    """Derive an Aptos address from a Solana wallet address (base58, used as-is)."""
    return _derive_aptos_address(_SOL_AUTH_FN, sol_address)
