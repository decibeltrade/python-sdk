from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from decibel._constants import (
    CompatVersion,
    DecibelConfig,
    Deployment,
    Network,
)

TEST_PACKAGE = "0x" + "ab" * 32
TEST_USDC = "0x" + "cd" * 32
TEST_TESTC = "0x" + "ef" * 32
TEST_PERP_ENGINE = "0x" + "12" * 32
TEST_SPOT_ENGINE = "0x" + "34" * 32
TEST_FULLNODE_URL = "https://test-node.example.com/v1"
TEST_TRADING_HTTP_URL = "https://test-trading.example.com"
TEST_TRADING_WS_URL = "wss://test-trading.example.com/ws"
TEST_GAS_STATION_URL = "https://test-gas.example.com"


@pytest.fixture
def test_deployment() -> Deployment:
    return Deployment(
        package=TEST_PACKAGE,
        usdc=TEST_USDC,
        testc=TEST_TESTC,
        perp_engine_global=TEST_PERP_ENGINE,
        spot_engine_global=TEST_SPOT_ENGINE,
    )


@pytest.fixture
def test_config(test_deployment: Deployment) -> DecibelConfig:
    return DecibelConfig(
        network=Network.TESTNET,
        fullnode_url=TEST_FULLNODE_URL,
        trading_http_url=TEST_TRADING_HTTP_URL,
        trading_ws_url=TEST_TRADING_WS_URL,
        gas_station_url=TEST_GAS_STATION_URL,
        gas_station_api_key="test-api-key",
        deployment=test_deployment,
        chain_id=2,
        compat_version=CompatVersion.V0_4,
    )


@pytest.fixture
def test_config_no_gas_key(test_deployment: Deployment) -> DecibelConfig:
    return DecibelConfig(
        network=Network.TESTNET,
        fullnode_url=TEST_FULLNODE_URL,
        trading_http_url=TEST_TRADING_HTTP_URL,
        trading_ws_url=TEST_TRADING_WS_URL,
        gas_station_url=TEST_GAS_STATION_URL,
        gas_station_api_key=None,
        deployment=test_deployment,
        chain_id=2,
        compat_version=CompatVersion.V0_4,
    )


@pytest.fixture
def mock_account() -> MagicMock:
    account = MagicMock()
    account.address.return_value = MagicMock()
    account.address.return_value.__str__ = lambda self: "0x" + "aa" * 32
    account.private_key = MagicMock()
    account.public_key.return_value = MagicMock()
    return account


def make_httpx_response(
    status_code: int = 200,
    json_data: Any = None,
    text: str = "",
    reason_phrase: str = "OK",
) -> httpx.Response:
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        text=text if not json_data else "",
        request=httpx.Request("GET", "https://test.example.com"),
    )
    return response


@pytest.fixture
def mock_async_client() -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_sync_client() -> MagicMock:
    client = MagicMock(spec=httpx.Client)
    client.close = MagicMock()
    return client


@pytest.fixture
def abi_registry() -> Any:
    from decibel.abi import AbiRegistry

    return AbiRegistry()
