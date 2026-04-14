"""Tests for decibel._gas_price_manager module."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel._gas_price_manager import (
    GasPriceInfo,
    GasPriceManager,
    GasPriceManagerOptions,
    GasPriceManagerSync,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(gas_estimate: int = 100, is_success: bool = True) -> MagicMock:
    mock_response = MagicMock()
    mock_response.is_success = is_success
    mock_response.json.return_value = {"gas_estimate": gas_estimate}
    mock_response.status_code = 200 if is_success else 500
    mock_response.text = "" if is_success else "Internal Server Error"
    return mock_response


# ---------------------------------------------------------------------------
# GasPriceManagerOptions
# ---------------------------------------------------------------------------


class TestGasPriceManagerOptions:
    def test_default_values(self) -> None:
        opts = GasPriceManagerOptions()
        assert opts.node_api_key is None
        assert opts.multiplier == 2.0
        assert opts.refresh_interval_seconds == 60.0
        assert opts.http_client is None
        assert opts.http_client_sync is None

    def test_custom_values(self) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        sync_client = MagicMock(spec=httpx.Client)
        opts = GasPriceManagerOptions(
            node_api_key="my-key",
            multiplier=3.0,
            refresh_interval_seconds=30.0,
            http_client=async_client,
            http_client_sync=sync_client,
        )
        assert opts.node_api_key == "my-key"
        assert opts.multiplier == 3.0
        assert opts.refresh_interval_seconds == 30.0
        assert opts.http_client is async_client
        assert opts.http_client_sync is sync_client

    def test_http_client_fields_accept_none(self) -> None:
        opts = GasPriceManagerOptions(http_client=None, http_client_sync=None)
        assert opts.http_client is None
        assert opts.http_client_sync is None


# ---------------------------------------------------------------------------
# GasPriceInfo
# ---------------------------------------------------------------------------


class TestGasPriceInfo:
    def test_stores_fields(self) -> None:
        info = GasPriceInfo(gas_estimate=200, timestamp=12345.0)
        assert info.gas_estimate == 200
        assert info.timestamp == 12345.0


# ---------------------------------------------------------------------------
# GasPriceManager (async)
# ---------------------------------------------------------------------------


class TestGasPriceManagerInit:
    def test_default_state(self, test_config: object) -> None:
        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        assert mgr._gas_price is None
        assert mgr._refresh_task is None
        assert mgr._pending_refresh_task is None
        assert not mgr._is_initialized
        assert mgr._multiplier == 2.0
        assert mgr._refresh_interval_seconds == 60.0
        assert mgr._http_client is None

    def test_stores_http_client_from_opts(self, test_config: object) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        opts = GasPriceManagerOptions(http_client=client)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]
        assert mgr._http_client is client

    def test_get_gas_price_returns_none_when_not_set(self, test_config: object) -> None:
        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        assert mgr.get_gas_price() is None
        assert mgr.gas_price is None

    def test_is_initialized_false_by_default(self, test_config: object) -> None:
        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        assert not mgr.is_initialized


class TestGasPriceManagerFetchGasPriceEstimation:
    async def test_with_shared_client(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        result = await mgr.fetch_gas_price_estimation()

        assert result == 100
        client.get.assert_called_once()
        call_kwargs = client.get.call_args
        assert call_kwargs.kwargs["timeout"] == 5.0

    async def test_without_client_creates_temp(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=50)
        mock_temp_client = AsyncMock()
        mock_temp_client.get = AsyncMock(return_value=mock_response)
        mock_temp_client.__aenter__ = AsyncMock(return_value=mock_temp_client)
        mock_temp_client.__aexit__ = AsyncMock(return_value=None)

        opts = GasPriceManagerOptions(multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        with patch("decibel._gas_price_manager.httpx.AsyncClient", return_value=mock_temp_client):
            result = await mgr.fetch_gas_price_estimation()

        assert result == 50

    async def test_applies_multiplier(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=2.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        result = await mgr.fetch_gas_price_estimation()
        assert result == 200

    async def test_error_response_raises(self, test_config: object) -> None:
        mock_response = _make_mock_response(is_success=False)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Failed to fetch gas price"):
            await mgr.fetch_gas_price_estimation()

    async def test_includes_auth_header_when_api_key_set(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, node_api_key="secret", multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        await mgr.fetch_gas_price_estimation()

        call_kwargs = client.get.call_args.kwargs
        assert call_kwargs["headers"] == {"x-api-key": "secret"}

    async def test_no_auth_header_when_no_api_key(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, node_api_key=None, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        await mgr.fetch_gas_price_estimation()

        call_kwargs = client.get.call_args.kwargs
        assert call_kwargs["headers"] == {}


class TestGasPriceManagerFetchAndSet:
    async def test_sets_gas_price_on_success(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        result = await mgr.fetch_and_set_gas_price()

        assert result == 100
        assert mgr._gas_price is not None
        assert mgr._gas_price.gas_estimate == 100

    async def test_raises_on_zero_estimate(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=0)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="no gas estimate"):
            await mgr.fetch_and_set_gas_price()

    async def test_raises_and_logs_on_error(self, test_config: object) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=ConnectionError("network failure"))

        opts = GasPriceManagerOptions(http_client=client)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        with pytest.raises(ConnectionError):
            await mgr.fetch_and_set_gas_price()


class TestGasPriceManagerGetGasPrice:
    async def test_returns_none_when_not_set(self, test_config: object) -> None:
        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        assert mgr.get_gas_price() is None

    async def test_returns_gas_estimate_when_set(self, test_config: object) -> None:
        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        mgr._gas_price = GasPriceInfo(gas_estimate=500, timestamp=time.time())
        assert mgr.get_gas_price() == 500


class TestGasPriceManagerInitialize:
    async def test_initialize_calls_fetch_and_creates_task(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        await mgr.initialize()

        assert mgr._is_initialized
        assert mgr._refresh_task is not None
        mgr._refresh_task.cancel()

    async def test_already_initialized_is_noop(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        await mgr.initialize()
        first_task = mgr._refresh_task
        call_count = client.get.call_count

        await mgr.initialize()

        assert mgr._refresh_task is first_task
        assert client.get.call_count == call_count
        mgr._refresh_task.cancel()

    async def test_initialize_logs_on_failure(self, test_config: object) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=RuntimeError("boom"))

        opts = GasPriceManagerOptions(http_client=client)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        # Should not raise; logs instead
        await mgr.initialize()
        assert not mgr._is_initialized


class TestGasPriceManagerDestroy:
    async def test_destroy_cancels_task_and_clears_state(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        await mgr.initialize()
        assert mgr._is_initialized

        await mgr.destroy()

        assert not mgr._is_initialized
        assert mgr._gas_price is None
        assert mgr._refresh_task is None

    async def test_destroy_with_no_task_is_safe(self, test_config: object) -> None:
        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        await mgr.destroy()  # Should not raise


class TestGasPriceManagerRefresh:
    async def test_refresh_creates_pending_task(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        mgr.refresh()
        assert mgr._pending_refresh_task is not None
        # Let it complete
        await asyncio.sleep(0)

    async def test_refresh_noop_when_task_already_pending(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        mgr.refresh()
        first_task = mgr._pending_refresh_task
        mgr.refresh()

        # Should be the same task (not done yet)
        assert mgr._pending_refresh_task is first_task
        await asyncio.sleep(0)


class TestGasPriceManagerRefreshLoop:
    async def test_refresh_loop_calls_fetch_periodically(self, test_config: object) -> None:
        call_count = 0

        async def fake_fetch_and_set() -> int:
            nonlocal call_count
            call_count += 1
            return 100

        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        mgr._refresh_interval_seconds = 0.01
        mgr.fetch_and_set_gas_price = fake_fetch_and_set  # type: ignore[method-assign]

        task = asyncio.create_task(mgr._refresh_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert call_count >= 1

    async def test_refresh_loop_continues_on_exception(self, test_config: object) -> None:
        call_count = 0

        async def flaky_fetch() -> int:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("transient error")

        mgr = GasPriceManager(test_config)  # type: ignore[arg-type]
        mgr._refresh_interval_seconds = 0.01
        mgr.fetch_and_set_gas_price = flaky_fetch  # type: ignore[method-assign]

        task = asyncio.create_task(mgr._refresh_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert call_count >= 1


class TestGasPriceManagerContextManager:
    async def test_aenter_calls_initialize(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        async with mgr as ctx:
            assert ctx is mgr
            assert mgr._is_initialized

    async def test_aexit_calls_destroy(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client=client, multiplier=1.0)
        mgr = GasPriceManager(test_config, opts=opts)  # type: ignore[arg-type]

        async with mgr:
            pass

        assert not mgr._is_initialized
        assert mgr._gas_price is None


# ---------------------------------------------------------------------------
# GasPriceManagerSync (threaded)
# ---------------------------------------------------------------------------


class TestGasPriceManagerSyncInit:
    def test_default_state(self, test_config: object) -> None:
        mgr = GasPriceManagerSync(test_config)  # type: ignore[arg-type]
        assert mgr._gas_price is None
        assert mgr._refresh_thread is None
        assert not mgr._is_initialized
        assert mgr._multiplier == 2.0
        assert mgr._http_client is None

    def test_stores_http_client_sync_from_opts(self, test_config: object) -> None:
        client = MagicMock(spec=httpx.Client)
        opts = GasPriceManagerOptions(http_client_sync=client)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]
        assert mgr._http_client is client


class TestGasPriceManagerSyncFetchGasPriceEstimation:
    def test_with_shared_client(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        result = mgr.fetch_gas_price_estimation()

        assert result == 100
        client.get.assert_called_once()
        call_kwargs = client.get.call_args.kwargs
        assert call_kwargs["timeout"] == 5.0

    def test_without_client_creates_temp(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=75)
        mock_temp_client = MagicMock()
        mock_temp_client.get = MagicMock(return_value=mock_response)
        mock_temp_client.__enter__ = MagicMock(return_value=mock_temp_client)
        mock_temp_client.__exit__ = MagicMock(return_value=None)

        opts = GasPriceManagerOptions(multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        with patch("decibel._gas_price_manager.httpx.Client", return_value=mock_temp_client):
            result = mgr.fetch_gas_price_estimation()

        assert result == 75

    def test_applies_multiplier(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=3.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        result = mgr.fetch_gas_price_estimation()
        assert result == 300

    def test_error_response_raises(self, test_config: object) -> None:
        mock_response = _make_mock_response(is_success=False)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Failed to fetch gas price"):
            mgr.fetch_gas_price_estimation()


class TestGasPriceManagerSyncFetchAndSet:
    def test_sets_gas_price_on_success(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=150)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        result = mgr.fetch_and_set_gas_price()

        assert result == 150
        assert mgr._gas_price is not None
        assert mgr._gas_price.gas_estimate == 150

    def test_raises_on_zero_estimate(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=0)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="no gas estimate"):
            mgr.fetch_and_set_gas_price()

    def test_raises_on_network_error(self, test_config: object) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(side_effect=ConnectionError("refused"))

        opts = GasPriceManagerOptions(http_client_sync=client)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        with pytest.raises(ConnectionError):
            mgr.fetch_and_set_gas_price()


class TestGasPriceManagerSyncGetGasPrice:
    def test_returns_none_when_not_set(self, test_config: object) -> None:
        mgr = GasPriceManagerSync(test_config)  # type: ignore[arg-type]
        assert mgr.get_gas_price() is None

    def test_returns_gas_estimate_when_set(self, test_config: object) -> None:
        mgr = GasPriceManagerSync(test_config)  # type: ignore[arg-type]
        mgr._gas_price = GasPriceInfo(gas_estimate=999, timestamp=time.time())
        assert mgr.get_gas_price() == 999


class TestGasPriceManagerSyncInitialize:
    def test_initialize_starts_daemon_thread(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        mgr.initialize()

        assert mgr._is_initialized
        assert mgr._refresh_thread is not None
        assert mgr._refresh_thread.daemon

        mgr.destroy()

    def test_already_initialized_is_noop(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        mgr.initialize()
        first_thread = mgr._refresh_thread
        call_count = client.get.call_count

        mgr.initialize()

        assert mgr._refresh_thread is first_thread
        assert client.get.call_count == call_count

        mgr.destroy()

    def test_initialize_logs_on_failure(self, test_config: object) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(side_effect=RuntimeError("fail"))

        opts = GasPriceManagerOptions(http_client_sync=client)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        # Should not raise; logs instead
        mgr.initialize()
        assert not mgr._is_initialized


class TestGasPriceManagerSyncDestroy:
    def test_destroy_sets_stop_event_and_joins_thread(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        mgr.initialize()
        assert mgr._is_initialized

        mgr.destroy()

        assert not mgr._is_initialized
        assert mgr._gas_price is None
        assert mgr._refresh_thread is None

    def test_destroy_with_no_thread_is_safe(self, test_config: object) -> None:
        mgr = GasPriceManagerSync(test_config)  # type: ignore[arg-type]
        mgr.destroy()  # Should not raise


class TestGasPriceManagerSyncRefresh:
    def test_refresh_calls_fetch_and_set(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        mgr.refresh()
        assert mgr._gas_price is not None

    def test_refresh_logs_on_exception(self, test_config: object) -> None:
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(side_effect=RuntimeError("boom"))

        opts = GasPriceManagerOptions(http_client_sync=client)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        # Should not raise
        mgr.refresh()


class TestGasPriceManagerSyncRefreshLoop:
    def test_refresh_loop_stops_on_event(self, test_config: object) -> None:
        call_count = 0

        def fake_fetch_and_set() -> int:
            nonlocal call_count
            call_count += 1
            return 100

        mgr = GasPriceManagerSync(test_config)  # type: ignore[arg-type]
        mgr._refresh_interval_seconds = 0.01
        mgr.fetch_and_set_gas_price = fake_fetch_and_set  # type: ignore[method-assign]

        thread = threading.Thread(target=mgr._refresh_loop, daemon=True)
        thread.start()
        time.sleep(0.05)
        mgr._stop_event.set()
        thread.join(timeout=1.0)

        assert call_count >= 1
        assert not thread.is_alive()


class TestGasPriceManagerSyncContextManager:
    def test_enter_calls_initialize(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        with mgr as ctx:
            assert ctx is mgr
            assert mgr._is_initialized

    def test_exit_calls_destroy(self, test_config: object) -> None:
        mock_response = _make_mock_response(gas_estimate=100)
        client = MagicMock(spec=httpx.Client)
        client.get = MagicMock(return_value=mock_response)

        opts = GasPriceManagerOptions(http_client_sync=client, multiplier=1.0)
        mgr = GasPriceManagerSync(test_config, opts=opts)  # type: ignore[arg-type]

        with mgr:
            pass

        assert not mgr._is_initialized
        assert mgr._gas_price is None
