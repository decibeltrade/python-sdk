"""Tests for decibel.read._base module (ReaderDeps, BaseReader)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from decibel.read._base import BaseReader, ReaderDeps

# ---------------------------------------------------------------------------
# Simple pydantic model for testing
# ---------------------------------------------------------------------------


class _SimpleModel(BaseModel):
    value: int


_SIMPLE_RETURN = (_SimpleModel(value=42), 200, "OK")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def reader_deps(test_config: object) -> ReaderDeps:
    return ReaderDeps(
        config=test_config,  # type: ignore[arg-type]
        ws=MagicMock(),
        aptos=MagicMock(),
        api_key="test-api-key",
        http_client=AsyncMock(spec=httpx.AsyncClient),
        http_client_sync=MagicMock(spec=httpx.Client),
    )


@pytest.fixture
def reader(reader_deps: ReaderDeps) -> BaseReader:
    return BaseReader(reader_deps)


# ---------------------------------------------------------------------------
# ReaderDeps
# ---------------------------------------------------------------------------


class TestReaderDeps:
    def test_required_fields(self, test_config: object) -> None:
        ws = MagicMock()
        aptos = MagicMock()
        deps = ReaderDeps(config=test_config, ws=ws, aptos=aptos)  # type: ignore[arg-type]
        assert deps.config is test_config
        assert deps.ws is ws
        assert deps.aptos is aptos

    def test_optional_api_key_defaults_to_none(self, test_config: object) -> None:
        deps = ReaderDeps(config=test_config, ws=MagicMock(), aptos=MagicMock())  # type: ignore[arg-type]
        assert deps.api_key is None

    def test_optional_http_client_defaults_to_none(self, test_config: object) -> None:
        deps = ReaderDeps(config=test_config, ws=MagicMock(), aptos=MagicMock())  # type: ignore[arg-type]
        assert deps.http_client is None

    def test_optional_http_client_sync_defaults_to_none(self, test_config: object) -> None:
        deps = ReaderDeps(config=test_config, ws=MagicMock(), aptos=MagicMock())  # type: ignore[arg-type]
        assert deps.http_client_sync is None

    def test_stores_all_optional_fields(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        sync_client = MagicMock(spec=httpx.Client)
        deps = ReaderDeps(
            config=test_config,  # type: ignore[arg-type]
            ws=MagicMock(),
            aptos=MagicMock(),
            api_key="key",
            http_client=async_client,
            http_client_sync=sync_client,
        )
        assert deps.api_key == "key"
        assert deps.http_client is async_client
        assert deps.http_client_sync is sync_client


# ---------------------------------------------------------------------------
# BaseReader properties
# ---------------------------------------------------------------------------


class TestBaseReaderProperties:
    def test_config_property(self, reader: BaseReader, reader_deps: ReaderDeps) -> None:
        assert reader.config is reader_deps.config

    def test_ws_property(self, reader: BaseReader, reader_deps: ReaderDeps) -> None:
        assert reader.ws is reader_deps.ws

    def test_aptos_property(self, reader: BaseReader, reader_deps: ReaderDeps) -> None:
        assert reader.aptos is reader_deps.aptos


# ---------------------------------------------------------------------------
# BaseReader.get_request
# ---------------------------------------------------------------------------


class TestBaseReaderGetRequest:
    async def test_get_request_delegates_to_utility(self, reader: BaseReader) -> None:
        with patch("decibel.read._base.get_request", return_value=_SIMPLE_RETURN) as mock_get:
            result = await reader.get_request(_SimpleModel, "https://example.com/api")
            mock_get.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                params=None,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client,
            )
            assert result == _SIMPLE_RETURN

    async def test_get_request_passes_params(self, reader: BaseReader) -> None:
        params = {"key": "value"}
        with patch("decibel.read._base.get_request", return_value=_SIMPLE_RETURN) as mock_get:
            await reader.get_request(_SimpleModel, "https://example.com/api", params=params)
            mock_get.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                params=params,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client,
            )


# ---------------------------------------------------------------------------
# BaseReader.post_request
# ---------------------------------------------------------------------------


class TestBaseReaderPostRequest:
    async def test_post_request_delegates_to_utility(self, reader: BaseReader) -> None:
        with patch("decibel.read._base.post_request", return_value=_SIMPLE_RETURN) as mock_post:
            body = {"data": 1}
            result = await reader.post_request(_SimpleModel, "https://example.com/api", body=body)
            mock_post.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                body=body,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client,
            )
            assert result == _SIMPLE_RETURN

    async def test_post_request_no_body(self, reader: BaseReader) -> None:
        with patch("decibel.read._base.post_request", return_value=_SIMPLE_RETURN) as mock_post:
            await reader.post_request(_SimpleModel, "https://example.com/api")
            mock_post.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                body=None,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client,
            )


# ---------------------------------------------------------------------------
# BaseReader.patch_request
# ---------------------------------------------------------------------------


class TestBaseReaderPatchRequest:
    async def test_patch_request_delegates_to_utility(self, reader: BaseReader) -> None:
        with patch("decibel.read._base.patch_request", return_value=_SIMPLE_RETURN) as mock_patch:
            body = {"update": True}
            result = await reader.patch_request(_SimpleModel, "https://example.com/api", body=body)
            mock_patch.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                body=body,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client,
            )
            assert result == _SIMPLE_RETURN


# ---------------------------------------------------------------------------
# BaseReader sync variants
# ---------------------------------------------------------------------------


class TestBaseReaderSyncVariants:
    def test_get_request_sync_delegates_to_utility(self, reader: BaseReader) -> None:
        with patch("decibel.read._base.get_request_sync", return_value=_SIMPLE_RETURN) as mock_get:
            result = reader.get_request_sync(_SimpleModel, "https://example.com/api")
            mock_get.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                params=None,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client_sync,
            )
            assert result == _SIMPLE_RETURN

    def test_get_request_sync_passes_params(self, reader: BaseReader) -> None:
        params = {"filter": "all"}
        with patch("decibel.read._base.get_request_sync", return_value=_SIMPLE_RETURN) as mock_get:
            reader.get_request_sync(_SimpleModel, "https://example.com/api", params=params)
            mock_get.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                params=params,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client_sync,
            )

    def test_post_request_sync_delegates_to_utility(self, reader: BaseReader) -> None:
        with patch(
            "decibel.read._base.post_request_sync", return_value=_SIMPLE_RETURN
        ) as mock_post:
            body = {"x": 1}
            result = reader.post_request_sync(_SimpleModel, "https://example.com/api", body=body)
            mock_post.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                body=body,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client_sync,
            )
            assert result == _SIMPLE_RETURN

    def test_patch_request_sync_delegates_to_utility(self, reader: BaseReader) -> None:
        with patch(
            "decibel.read._base.patch_request_sync", return_value=_SIMPLE_RETURN
        ) as mock_patch:
            body = {"y": 2}
            result = reader.patch_request_sync(_SimpleModel, "https://example.com/api", body=body)
            mock_patch.assert_called_once_with(
                model=_SimpleModel,
                url="https://example.com/api",
                body=body,
                api_key=reader._deps.api_key,
                client=reader._deps.http_client_sync,
            )
            assert result == _SIMPLE_RETURN
