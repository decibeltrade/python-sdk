"""Shared fixtures for API resource behavioral tests.

These tests verify the SDK's REST API readers produce correct HTTP requests
and parse responses according to the specification in docs/SPEC-REST.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import httpx
import pytest

from decibel._constants import TESTNET_CONFIG, DecibelConfig
from decibel.read._base import ReaderDeps
from decibel.read._ws import DecibelWsSubscription

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class CapturedRequest:
    """Captures the details of an HTTP request for assertion."""

    method: str
    url: str
    params: dict[str, str] | None
    headers: dict[str, str]


class MockTransport(httpx.AsyncBaseTransport):
    """Mock transport that captures requests and returns canned responses."""

    def __init__(self) -> None:
        self.captured_requests: list[CapturedRequest] = []
        self._responses: list[httpx.Response] = []

    def set_response(self, json_data: Any, status_code: int = 200) -> None:
        """Set the next response to return."""
        import json

        self._responses.append(
            httpx.Response(
                status_code=status_code,
                content=json.dumps(json_data).encode(),
                headers={"content-type": "application/json"},
            )
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.captured_requests.append(
            CapturedRequest(
                method=request.method,
                url=str(request.url),
                params=dict(request.url.params) if request.url.params else None,
                headers=dict(request.headers),
            )
        )
        if self._responses:
            return self._responses.pop(0)
        return httpx.Response(200, content=b"[]", headers={"content-type": "application/json"})


@pytest.fixture
def testnet_config() -> DecibelConfig:
    """Provide testnet configuration."""
    return TESTNET_CONFIG


@pytest.fixture
def mock_transport() -> MockTransport:
    """Provide a mock transport for capturing HTTP requests."""
    return MockTransport()


@pytest.fixture
def mock_ws() -> DecibelWsSubscription:
    """Provide a mock WebSocket subscription."""
    ws = AsyncMock(spec=DecibelWsSubscription)
    return ws


@pytest.fixture
def reader_deps(
    testnet_config: DecibelConfig,
    mock_ws: DecibelWsSubscription,
) -> ReaderDeps:
    """Provide reader dependencies with mocked WS and API key."""
    return ReaderDeps(
        config=testnet_config,
        ws=mock_ws,
        aptos=AsyncMock(),
        api_key="test-api-key-123",
    )


@pytest.fixture
async def transport_deps(
    testnet_config: DecibelConfig,
    mock_ws: DecibelWsSubscription,
    mock_transport: MockTransport,
) -> AsyncIterator[ReaderDeps]:
    """Reader dependencies whose HTTP client speaks to ``mock_transport``.

    Unlike patching ``get_request``, this exercises the real request path, so the captured
    request carries the URL, query params and auth headers the SDK actually emits.
    """
    async with httpx.AsyncClient(transport=mock_transport) as client:
        yield ReaderDeps(
            config=testnet_config,
            ws=mock_ws,
            aptos=AsyncMock(),
            api_key="test-api-key-123",
            http_client=client,
        )
