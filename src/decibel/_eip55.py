"""Minimal keccak-256 + EIP-55 checksum — zero external dependencies.

Note: EIP-55 requires the original Keccak-256 (padding byte 0x01), which is
distinct from NIST SHA3-256 (padding byte 0x06) available via ``hashlib``.
"""

from __future__ import annotations

import re

__all__ = ["to_checksum_address"]

_MASK64 = (1 << 64) - 1
_RATE = 136  # bytes (keccak-256 rate = 1600 - 2*256 bits)

# Round constants for keccak-f[1600].
_RC: tuple[int, ...] = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)

# rho rotation offsets indexed by [x + 5y].
_ROT: tuple[int, ...] = (
    0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43,
    25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56, 14,
)  # fmt: skip


def _rot64(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _MASK64


def _keccak_f(s: list[int]) -> None:
    for r in range(24):
        # theta — column parity
        c = [s[x] ^ s[x + 5] ^ s[x + 10] ^ s[x + 15] ^ s[x + 20] for x in range(5)]
        d = [c[(x + 4) % 5] ^ _rot64(c[(x + 1) % 5], 1) for x in range(5)]
        for y in range(0, 25, 5):
            for x in range(5):
                s[y + x] ^= d[x]

        # rho + pi — rotate lanes and move to new positions
        t = [0] * 25
        for x in range(5):
            for y in range(5):
                i = x + 5 * y
                t[y + 5 * ((2 * x + 3 * y) % 5)] = _rot64(s[i], _ROT[i])

        # chi — non-linear step
        for y in range(0, 25, 5):
            t0, t1, t2, t3, t4 = t[y], t[y + 1], t[y + 2], t[y + 3], t[y + 4]
            s[y] = t0 ^ ((~t1 & _MASK64) & t2)
            s[y + 1] = t1 ^ ((~t2 & _MASK64) & t3)
            s[y + 2] = t2 ^ ((~t3 & _MASK64) & t4)
            s[y + 3] = t3 ^ ((~t4 & _MASK64) & t0)
            s[y + 4] = t4 ^ ((~t0 & _MASK64) & t1)

        # iota — round constant
        s[0] ^= _RC[r]


def _keccak256_hex(data: bytes) -> str:
    """Keccak-256 hash -> hex string (no 0x prefix)."""
    # Pad: data || 0x01 || 0x00...0x00 || 0x80 (keccak padding, NOT SHA-3 0x06).
    blocks = (len(data) + 1 + _RATE - 1) // _RATE
    padded = bytearray(blocks * _RATE)
    padded[: len(data)] = data
    padded[len(data)] = 0x01
    padded[-1] |= 0x80

    s = [0] * 25
    for off in range(0, len(padded), _RATE):
        for i in range(17):
            s[i] ^= int.from_bytes(padded[off + i * 8 : off + i * 8 + 8], "little")
        _keccak_f(s)

    out = b"".join(s[i].to_bytes(8, "little") for i in range(4))
    return out.hex()


_ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def to_checksum_address(address: str) -> str:
    """EIP-55 mixed-case checksum encoding for Ethereum addresses.

    Equivalent to ``getAddress`` from ethers — zero dependencies.

    See https://eips.ethereum.org/EIPS/eip-55
    """
    if not _ETH_ADDRESS_RE.match(address):
        raise ValueError(f"Invalid Ethereum address: {address}")

    lower = address[2:].lower()
    hash_hex = _keccak256_hex(lower.encode("ascii"))

    out = ["0x"]
    for i in range(40):
        # Hex digits a-f are uppercased when the corresponding hash nibble >= 8.
        out.append(lower[i].upper() if int(hash_hex[i], 16) >= 8 else lower[i])
    return "".join(out)
