from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aptos_sdk.account_address import AccountAddress

__all__ = [
    "Network",
    "CompatVersion",
    "Deployment",
    "DecibelConfig",
    "DEFAULT_COMPAT_VERSION",
    "MAINNET_CONFIG",
    "NETNA_CONFIG",
    "TESTNET_CONFIG",
    "LOCAL_CONFIG",
    "DOCKER_CONFIG",
    "NAMED_CONFIGS",
    "get_usdc_address",
    "get_testc_address",
    "get_perp_engine_global_address",
]


class Network(str, Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    CUSTOM = "custom"


class CompatVersion(str, Enum):
    V0_4 = "v0.4"  # decibel-testnet-release-v0.4 - and final version.


@dataclass(frozen=True)
class Deployment:
    package: str
    usdc: str
    testc: str
    perp_engine_global: str


@dataclass(frozen=True)
class DecibelConfig:
    network: Network
    fullnode_url: str
    trading_http_url: str
    trading_ws_url: str
    gas_station_url: str | None
    gas_station_api_key: str | None
    deployment: Deployment
    chain_id: int | None
    compat_version: CompatVersion


DEFAULT_COMPAT_VERSION = CompatVersion.V0_4


def get_usdc_address(package: str) -> str:
    creator = AccountAddress.from_str(package)
    return str(AccountAddress.for_named_object(creator, b"USDC"))


def get_testc_address(package: str) -> str:
    creator = AccountAddress.from_str(package)
    return str(AccountAddress.for_named_object(creator, b"TESTC"))


def get_perp_engine_global_address(package: str) -> str:
    creator = AccountAddress.from_str(package)
    return str(AccountAddress.for_named_object(creator, b"GlobalPerpEngine"))


def _create_deployment(package: str) -> Deployment:
    return Deployment(
        package=package,
        usdc=get_usdc_address(package),
        testc=get_testc_address(package),
        perp_engine_global=get_perp_engine_global_address(package),
    )


_MAINNET_PACKAGE = "0xe6683d451db246750f180fb78d9b5e0a855dacba64ddf5810dffdaeb221e46bf"
_MAINNET_USDC = "0xbae207659db88bea0cbead6da0ed00aac12edcdda169e591cd41c94180b46f3b"
_NETNA_PACKAGE = "0xb8a5788314451ce4d2fbbad32e1bad88d4184b73943b7fe5166eab93cf1a5a95"
_TESTNET_PACKAGE = "0x952535c3049e52f195f26798c2f1340d7dd5100edbe0f464e520a974d16fbe9f"
_LOCAL_PACKAGE = "0xb8a5788314451ce4d2fbbad32e1bad88d4184b73943b7fe5166eab93cf1a5a95"
_DOCKER_PACKAGE = "0xb8a5788314451ce4d2fbbad32e1bad88d4184b73943b7fe5166eab93cf1a5a95"

MAINNET_DEPLOYMENT = Deployment(
    package=_MAINNET_PACKAGE,
    usdc=_MAINNET_USDC,
    testc=get_testc_address(_MAINNET_PACKAGE),
    perp_engine_global=get_perp_engine_global_address(_MAINNET_PACKAGE),
)

MAINNET_CONFIG = DecibelConfig(
    network=Network.MAINNET,
    fullnode_url="https://api.mainnet.aptoslabs.com/v1",
    trading_http_url="https://api.mainnet.aptoslabs.com/decibel",
    trading_ws_url="wss://api.mainnet.aptoslabs.com/decibel/ws",
    gas_station_url="https://api.mainnet.aptoslabs.com/gs/v1",
    gas_station_api_key=None,
    deployment=MAINNET_DEPLOYMENT,
    chain_id=1,
    compat_version=CompatVersion.V0_4,
)

NETNA_CONFIG = DecibelConfig(
    network=Network.CUSTOM,
    fullnode_url="https://api.netna.staging.aptoslabs.com/v1",
    trading_http_url="https://api.netna.staging.aptoslabs.com/decibel",
    trading_ws_url="wss://api.netna.staging.aptoslabs.com/decibel/ws",
    gas_station_url="https://api.netna.staging.aptoslabs.com/gs/v1",
    gas_station_api_key=None,
    deployment=_create_deployment(_NETNA_PACKAGE),
    chain_id=208,
    compat_version=CompatVersion.V0_4,
)

TESTNET_CONFIG = DecibelConfig(
    network=Network.TESTNET,
    fullnode_url="https://api.testnet.aptoslabs.com/v1",
    trading_http_url="https://api.testnet.aptoslabs.com/decibel",
    trading_ws_url="wss://api.testnet.aptoslabs.com/decibel/ws",
    gas_station_url="https://api.testnet.aptoslabs.com/gs/v1",
    gas_station_api_key=None,
    deployment=_create_deployment(_TESTNET_PACKAGE),
    chain_id=2,
    compat_version=CompatVersion.V0_4,
)

LOCAL_CONFIG = DecibelConfig(
    network=Network.CUSTOM,
    fullnode_url="http://localhost:8080/v1",
    trading_http_url="http://localhost:8084",
    trading_ws_url="ws://localhost:8083",
    gas_station_url="http://localhost:8085",
    gas_station_api_key=None,
    deployment=_create_deployment(_LOCAL_PACKAGE),
    chain_id=None,
    compat_version=CompatVersion.V0_4,
)

DOCKER_CONFIG = DecibelConfig(
    network=Network.CUSTOM,
    fullnode_url="http://tradenet:8080/v1",
    trading_http_url="http://trading-api-http:8080",
    trading_ws_url="ws://trading-api-ws:8080",
    gas_station_url="http://fee-payer:8080",
    gas_station_api_key=None,
    deployment=_create_deployment(_DOCKER_PACKAGE),
    chain_id=None,
    compat_version=CompatVersion.V0_4,
)

NAMED_CONFIGS: dict[str, DecibelConfig] = {
    "mainnet": MAINNET_CONFIG,
    "netna": NETNA_CONFIG,
    "testnet": TESTNET_CONFIG,
    "local": LOCAL_CONFIG,
    "docker": DOCKER_CONFIG,
}
