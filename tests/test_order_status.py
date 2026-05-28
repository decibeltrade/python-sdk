"""Tests for decibel._order_status module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from decibel._order_status import OrderStatus, OrderStatusClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORDER_STATUS_DATA = {
    "parent": "0xparent",
    "market": "0xmarket",
    "order_id": "0xorder",
    "status": "Filled",
    "orig_size": 1.0,
    "remaining_size": 0.0,
    "size_delta": 1.0,
    "price": 100.0,
    "is_buy": True,
    "details": "ok",
    "transaction_version": 1,
    "unix_ms": 1000,
}


def _make_async_response(
    status_code: int = 200,
    json_data: dict | None = None,
    is_success: bool = True,
) -> AsyncMock:
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = is_success
    resp.json.return_value = json_data or ORDER_STATUS_DATA
    resp.text = ""
    resp.reason_phrase = "OK" if is_success else "Error"
    return resp


def _make_sync_response(
    status_code: int = 200,
    json_data: dict | None = None,
    is_success: bool = True,
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = is_success
    resp.json.return_value = json_data or ORDER_STATUS_DATA
    resp.text = ""
    resp.reason_phrase = "OK" if is_success else "Error"
    return resp


# ---------------------------------------------------------------------------
# OrderStatusClient.__init__
# ---------------------------------------------------------------------------


class TestOrderStatusClientInit:
    def test_stores_config(self, test_config: object) -> None:
        client = OrderStatusClient(test_config)  # type: ignore[arg-type]
        assert client._config is test_config

    def test_optional_clients_default_to_none(self, test_config: object) -> None:
        client = OrderStatusClient(test_config)  # type: ignore[arg-type]
        assert client._http_client is None
        assert client._http_client_sync is None

    def test_stores_provided_clients(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        sync_client = MagicMock(spec=httpx.Client)
        client = OrderStatusClient(
            test_config,  # type: ignore[arg-type]
            http_client=async_client,
            http_client_sync=sync_client,
        )
        assert client._http_client is async_client
        assert client._http_client_sync is sync_client


# ---------------------------------------------------------------------------
# get_order_status (async)
# ---------------------------------------------------------------------------


class TestGetOrderStatus:
    async def test_success_returns_order_status(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        async_client.get = AsyncMock(return_value=_make_async_response())

        os_client = OrderStatusClient(test_config, http_client=async_client)  # type: ignore[arg-type]
        result = await os_client.get_order_status("0xorder", "0xmarket", "0xuser")

        assert isinstance(result, OrderStatus)
        assert result.order_id == "0xorder"

    async def test_404_returns_none(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_async_response(status_code=404, is_success=False)
        resp.status_code = 404
        async_client.get = AsyncMock(return_value=resp)

        os_client = OrderStatusClient(test_config, http_client=async_client)  # type: ignore[arg-type]
        result = await os_client.get_order_status("0xorder", "0xmarket", "0xuser")

        assert result is None

    async def test_server_error_logs_and_returns_none(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        resp = _make_async_response(status_code=500, is_success=False)
        resp.status_code = 500
        resp.reason_phrase = "Internal Server Error"
        async_client.get = AsyncMock(return_value=resp)

        os_client = OrderStatusClient(test_config, http_client=async_client)  # type: ignore[arg-type]
        result = await os_client.get_order_status("0xorder", "0xmarket", "0xuser")

        assert result is None

    async def test_uses_shared_client_when_available(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        async_client.get = AsyncMock(return_value=_make_async_response())

        os_client = OrderStatusClient(test_config, http_client=async_client)  # type: ignore[arg-type]
        await os_client.get_order_status("0xorder", "0xmarket", "0xuser")

        async_client.get.assert_called_once()

    async def test_uses_explicit_client_parameter(self, test_config: object) -> None:
        stored_client = AsyncMock(spec=httpx.AsyncClient)
        explicit_client = AsyncMock(spec=httpx.AsyncClient)
        explicit_client.get = AsyncMock(return_value=_make_async_response())

        os_client = OrderStatusClient(test_config, http_client=stored_client)  # type: ignore[arg-type]
        await os_client.get_order_status("0xorder", "0xmarket", "0xuser", client=explicit_client)

        explicit_client.get.assert_called_once()
        stored_client.get.assert_not_called()

    async def test_creates_temp_client_when_no_client(self, test_config: object) -> None:
        mock_temp = AsyncMock()
        mock_temp.get = AsyncMock(return_value=_make_async_response())
        mock_temp.__aenter__ = AsyncMock(return_value=mock_temp)
        mock_temp.__aexit__ = AsyncMock(return_value=None)

        os_client = OrderStatusClient(test_config)  # type: ignore[arg-type]

        with patch("decibel._order_status.httpx.AsyncClient", return_value=mock_temp):
            result = await os_client.get_order_status("0xorder", "0xmarket", "0xuser")

        assert isinstance(result, OrderStatus)

    async def test_exception_logs_and_returns_none(self, test_config: object) -> None:
        async_client = AsyncMock(spec=httpx.AsyncClient)
        async_client.get = AsyncMock(side_effect=ConnectionError("connection refused"))

        os_client = OrderStatusClient(test_config, http_client=async_client)  # type: ignore[arg-type]
        result = await os_client.get_order_status("0xorder", "0xmarket", "0xuser")

        assert result is None


# ---------------------------------------------------------------------------
# get_order_status_sync
# ---------------------------------------------------------------------------


class TestGetOrderStatusSync:
    def test_success_returns_order_status(self, test_config: object) -> None:
        sync_client = MagicMock(spec=httpx.Client)
        sync_client.get = MagicMock(return_value=_make_sync_response())

        os_client = OrderStatusClient(test_config, http_client_sync=sync_client)  # type: ignore[arg-type]
        result = os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser")

        assert isinstance(result, OrderStatus)

    def test_404_returns_none(self, test_config: object) -> None:
        sync_client = MagicMock(spec=httpx.Client)
        resp = _make_sync_response(status_code=404, is_success=False)
        resp.status_code = 404
        sync_client.get = MagicMock(return_value=resp)

        os_client = OrderStatusClient(test_config, http_client_sync=sync_client)  # type: ignore[arg-type]
        result = os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser")

        assert result is None

    def test_server_error_logs_and_returns_none(self, test_config: object) -> None:
        sync_client = MagicMock(spec=httpx.Client)
        resp = _make_sync_response(status_code=500, is_success=False)
        resp.status_code = 500
        resp.reason_phrase = "Internal Server Error"
        sync_client.get = MagicMock(return_value=resp)

        os_client = OrderStatusClient(test_config, http_client_sync=sync_client)  # type: ignore[arg-type]
        result = os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser")

        assert result is None

    def test_uses_shared_sync_client(self, test_config: object) -> None:
        sync_client = MagicMock(spec=httpx.Client)
        sync_client.get = MagicMock(return_value=_make_sync_response())

        os_client = OrderStatusClient(test_config, http_client_sync=sync_client)  # type: ignore[arg-type]
        os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser")

        sync_client.get.assert_called_once()

    def test_uses_explicit_client_parameter(self, test_config: object) -> None:
        stored_client = MagicMock(spec=httpx.Client)
        explicit_client = MagicMock(spec=httpx.Client)
        explicit_client.get = MagicMock(return_value=_make_sync_response())

        os_client = OrderStatusClient(test_config, http_client_sync=stored_client)  # type: ignore[arg-type]
        os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser", client=explicit_client)

        explicit_client.get.assert_called_once()
        stored_client.get.assert_not_called()

    def test_creates_temp_client_when_no_client(self, test_config: object) -> None:
        mock_temp = MagicMock()
        mock_temp.get = MagicMock(return_value=_make_sync_response())
        mock_temp.__enter__ = MagicMock(return_value=mock_temp)
        mock_temp.__exit__ = MagicMock(return_value=None)

        os_client = OrderStatusClient(test_config)  # type: ignore[arg-type]

        with patch("decibel._order_status.httpx.Client", return_value=mock_temp):
            result = os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser")

        assert isinstance(result, OrderStatus)

    def test_exception_logs_and_returns_none(self, test_config: object) -> None:
        sync_client = MagicMock(spec=httpx.Client)
        sync_client.get = MagicMock(side_effect=ConnectionError("refused"))

        os_client = OrderStatusClient(test_config, http_client_sync=sync_client)  # type: ignore[arg-type]
        result = os_client.get_order_status_sync("0xorder", "0xmarket", "0xuser")

        assert result is None


# ---------------------------------------------------------------------------
# parse_order_status_type
# ---------------------------------------------------------------------------


class TestParseOrderStatusType:
    def test_acknowledged(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Acknowledged") == "Acknowledged"

    def test_acknowledged_case_insensitive(self) -> None:
        assert OrderStatusClient.parse_order_status_type("ACKNOWLEDGED") == "Acknowledged"

    def test_filled(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Filled") == "Filled"

    def test_filled_case_insensitive(self) -> None:
        assert OrderStatusClient.parse_order_status_type("filled") == "Filled"

    def test_cancelled(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Cancelled") == "Cancelled"

    def test_rejected(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Rejected") == "Rejected"

    def test_unknown_for_unrecognized_string(self) -> None:
        assert OrderStatusClient.parse_order_status_type("SomethingElse") == "Unknown"

    def test_none_returns_unknown(self) -> None:
        assert OrderStatusClient.parse_order_status_type(None) == "Unknown"

    def test_empty_string_returns_unknown(self) -> None:
        assert OrderStatusClient.parse_order_status_type("") == "Unknown"

    def test_partial_match_cancelled(self) -> None:
        assert OrderStatusClient.parse_order_status_type("order_cancelled_by_user") == "Cancelled"


# ---------------------------------------------------------------------------
# is_success_status / is_failure_status / is_final_status
# ---------------------------------------------------------------------------


class TestStatusHelpers:
    def test_is_success_status_true_for_filled(self) -> None:
        assert OrderStatusClient.is_success_status("Filled") is True

    def test_is_success_status_false_for_acknowledged(self) -> None:
        assert OrderStatusClient.is_success_status("Acknowledged") is False

    def test_is_success_status_false_for_cancelled(self) -> None:
        assert OrderStatusClient.is_success_status("Cancelled") is False

    def test_is_success_status_false_for_none(self) -> None:
        assert OrderStatusClient.is_success_status(None) is False

    def test_is_failure_status_true_for_cancelled(self) -> None:
        assert OrderStatusClient.is_failure_status("Cancelled") is True

    def test_is_failure_status_true_for_rejected(self) -> None:
        assert OrderStatusClient.is_failure_status("Rejected") is True

    def test_is_failure_status_false_for_filled(self) -> None:
        assert OrderStatusClient.is_failure_status("Filled") is False

    def test_is_failure_status_false_for_acknowledged(self) -> None:
        assert OrderStatusClient.is_failure_status("Acknowledged") is False

    def test_is_failure_status_false_for_none(self) -> None:
        assert OrderStatusClient.is_failure_status(None) is False

    def test_is_final_status_true_for_filled(self) -> None:
        assert OrderStatusClient.is_final_status("Filled") is True

    def test_is_final_status_true_for_cancelled(self) -> None:
        assert OrderStatusClient.is_final_status("Cancelled") is True

    def test_is_final_status_true_for_rejected(self) -> None:
        assert OrderStatusClient.is_final_status("Rejected") is True

    def test_is_final_status_false_for_acknowledged(self) -> None:
        assert OrderStatusClient.is_final_status("Acknowledged") is False

    def test_is_final_status_false_for_unknown(self) -> None:
        assert OrderStatusClient.is_final_status("Unknown") is False

    def test_is_final_status_false_for_none(self) -> None:
        assert OrderStatusClient.is_final_status(None) is False
