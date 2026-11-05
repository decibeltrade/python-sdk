from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from decibel._base import BaseSDK, BaseSDKOptions
from decibel.read import DecibelReadDex


@pytest.mark.parametrize("provided_client", [False, True])
@pytest.mark.parametrize("exit_mode", ["close", "context", "exception"])
async def test_base_closes_owned_clients(
    test_config: Any, mock_account: Any, provided_client: bool, exit_mode: str
) -> None:
    client = httpx.AsyncClient() if provided_client else None
    sdk = BaseSDK(test_config, mock_account, BaseSDKOptions(http_client=client))
    try:
        if exit_mode == "close":
            await sdk.close()
        elif exit_mode == "context":
            async with sdk:
                pass
        else:
            with pytest.raises(ValueError, match="body failed"):
                async with sdk:
                    raise ValueError("body failed")

        assert sdk.aptos.client.is_closed
        assert sdk._http_client.is_closed is not provided_client
    finally:
        await sdk.aptos.close()
        await sdk._http_client.aclose()


@pytest.mark.parametrize("exit_mode", ["close", "context", "exception"])
async def test_reader_closes_owned_clients(test_config: Any, exit_mode: str) -> None:
    sdk = DecibelReadDex(test_config)
    try:
        if exit_mode == "close":
            await sdk.close()
        elif exit_mode == "context":
            async with sdk:
                pass
        else:
            with pytest.raises(ValueError, match="body failed"):
                async with sdk:
                    raise ValueError("body failed")

        assert sdk._aptos.client.is_closed
        assert sdk._http_client.is_closed
    finally:
        await sdk._aptos.close()
        await sdk._http_client.aclose()


async def test_base_closes_http_client_when_aptos_close_fails(
    test_config: Any, mock_account: Any
) -> None:
    sdk = BaseSDK(test_config, mock_account)
    try:
        with patch.object(sdk.aptos, "close", AsyncMock(side_effect=ValueError("close failed"))):
            with pytest.raises(ValueError, match="close failed"):
                await sdk.close()
        assert sdk._http_client.is_closed
    finally:
        await sdk.aptos.close()
        await sdk._http_client.aclose()


@pytest.mark.parametrize("failure", ["websocket", "aptos"])
async def test_reader_finishes_cleanup_after_close_error(test_config: Any, failure: str) -> None:
    sdk = DecibelReadDex(test_config)
    target = sdk.ws if failure == "websocket" else sdk._aptos
    try:
        with patch.object(target, "close", AsyncMock(side_effect=ValueError("close failed"))):
            with pytest.raises(ValueError, match="close failed"):
                await sdk.close()
        assert sdk._http_client.is_closed
        if failure == "websocket":
            assert sdk._aptos.client.is_closed
    finally:
        await sdk._aptos.close()
        await sdk._http_client.aclose()
