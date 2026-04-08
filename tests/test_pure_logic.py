"""Unit tests for pure-logic and utility modules in the Decibel SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from decibel._exceptions import TxnConfirmError, TxnSubmitError
from decibel._gas_price_manager import _build_auth_headers
from decibel._order_status import OrderStatusClient
from decibel._pagination import construct_known_query_params
from decibel._utils import (
    FetchError,
    extract_vault_address_from_create_tx,
    get_request_sync,
    get_trading_competition_subaccount_addr,
    get_vault_share_address,
    patch_request_sync,
    post_request_sync,
    prettify_validation_error,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _DummyModel(BaseModel):
    value: str


@dataclass
class _SyncCapturedRequest:
    method: str
    url: str
    params: dict[str, str] | None
    headers: dict[str, str]


class SyncMockTransport(httpx.BaseTransport):
    """Synchronous mock transport mirroring the async MockTransport."""

    def __init__(self) -> None:
        self.captured_requests: list[_SyncCapturedRequest] = []
        self._responses: list[httpx.Response] = []

    def set_response(self, json_data: Any, status_code: int = 200) -> None:
        self._responses.append(
            httpx.Response(
                status_code=status_code,
                content=json.dumps(json_data).encode(),
                headers={"content-type": "application/json"},
            )
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.captured_requests.append(
            _SyncCapturedRequest(
                method=request.method,
                url=str(request.url),
                params=(dict(request.url.params) if request.url.params else None),
                headers=dict(request.headers),
            )
        )
        if self._responses:
            return self._responses.pop(0)
        return httpx.Response(
            200,
            content=b"[]",
            headers={"content-type": "application/json"},
        )


# ===================================================================
# 1. _pagination.construct_known_query_params
# ===================================================================


class TestConstructKnownQueryParams:
    def test_all_params_set(self) -> None:
        result = construct_known_query_params(
            {
                "limit": 10,
                "offset": 5,
                "search_term": "hello",
                "sort_key": "name",
                "sort_dir": "ASC",
            }
        )
        assert result == {
            "limit": "10",
            "offset": "5",
            "search_term": "hello",
            "sort_key": "name",
            "sort_dir": "ASC",
        }

    def test_some_params_set(self) -> None:
        result = construct_known_query_params({"limit": 20, "sort_key": "price"})
        assert result == {"limit": "20", "sort_key": "price"}

    def test_no_params(self) -> None:
        result = construct_known_query_params({})
        assert result == {}

    def test_none_values_skipped(self) -> None:
        result = construct_known_query_params({"limit": 5, "sort_dir": None})
        assert result == {"limit": "5"}
        assert "sort_dir" not in result

    def test_empty_string_skipped(self) -> None:
        result = construct_known_query_params({"search_term": "  "})
        assert result == {}

    def test_whitespace_only_skipped(self) -> None:
        result = construct_known_query_params({"search_term": "\t\n"})
        assert result == {}

    def test_non_empty_string_kept(self) -> None:
        result = construct_known_query_params({"search_term": " hi "})
        assert result == {"search_term": " hi "}


# ===================================================================
# 2. _order_status static helpers
# ===================================================================


class TestParseOrderStatusType:
    def test_acknowledged(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Acknowledged") == "Acknowledged"

    def test_acknowledged_case_insensitive(self) -> None:
        assert OrderStatusClient.parse_order_status_type("ACKNOWLEDGED") == "Acknowledged"

    def test_filled(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Filled") == "Filled"

    def test_cancelled(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Cancelled") == "Cancelled"

    def test_rejected(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Rejected") == "Rejected"

    def test_unknown_string(self) -> None:
        assert OrderStatusClient.parse_order_status_type("Pending") == "Unknown"

    def test_none_returns_unknown(self) -> None:
        assert OrderStatusClient.parse_order_status_type(None) == "Unknown"

    def test_empty_string_returns_unknown(self) -> None:
        assert OrderStatusClient.parse_order_status_type("") == "Unknown"

    def test_substring_match(self) -> None:
        assert OrderStatusClient.parse_order_status_type("order_filled_fully") == "Filled"


class TestIsSuccessStatus:
    def test_filled_is_success(self) -> None:
        assert OrderStatusClient.is_success_status("Filled") is True

    def test_cancelled_not_success(self) -> None:
        assert OrderStatusClient.is_success_status("Cancelled") is False

    def test_none_not_success(self) -> None:
        assert OrderStatusClient.is_success_status(None) is False


class TestIsFailureStatus:
    def test_cancelled_is_failure(self) -> None:
        assert OrderStatusClient.is_failure_status("Cancelled") is True

    def test_rejected_is_failure(self) -> None:
        assert OrderStatusClient.is_failure_status("Rejected") is True

    def test_filled_not_failure(self) -> None:
        assert OrderStatusClient.is_failure_status("Filled") is False

    def test_none_not_failure(self) -> None:
        assert OrderStatusClient.is_failure_status(None) is False


class TestIsFinalStatus:
    def test_filled_is_final(self) -> None:
        assert OrderStatusClient.is_final_status("Filled") is True

    def test_cancelled_is_final(self) -> None:
        assert OrderStatusClient.is_final_status("Cancelled") is True

    def test_rejected_is_final(self) -> None:
        assert OrderStatusClient.is_final_status("Rejected") is True

    def test_acknowledged_not_final(self) -> None:
        assert OrderStatusClient.is_final_status("Acknowledged") is False

    def test_none_not_final(self) -> None:
        assert OrderStatusClient.is_final_status(None) is False


# ===================================================================
# 3. _exceptions.TxnSubmitError
# ===================================================================


class TestTxnSubmitError:
    def test_basic_instantiation(self) -> None:
        err = TxnSubmitError("connection refused")
        assert str(err) == "connection refused"
        assert err.original_exception is None

    def test_with_original_exception(self) -> None:
        cause = TimeoutError("timed out")
        err = TxnSubmitError("submit failed", cause)
        assert err.original_exception is cause
        assert "submit failed" in str(err)

    def test_inherits_exception(self) -> None:
        err = TxnSubmitError("oops")
        assert isinstance(err, Exception)

    def test_with_none_original(self) -> None:
        err = TxnSubmitError("msg", None)
        assert err.original_exception is None


class TestTxnConfirmError:
    def test_basic_instantiation(self) -> None:
        err = TxnConfirmError("0xabc", "timeout")
        assert err.tx_hash == "0xabc"
        assert "0xabc" in str(err)
        assert "timeout" in str(err)


# ===================================================================
# 4. _utils pure functions
# ===================================================================


class TestPrettifyValidationError:
    def test_single_field_error(self) -> None:
        class _M(BaseModel):
            x: int

        try:
            _M.model_validate({"x": "not_an_int"})
        except ValidationError as e:
            result = prettify_validation_error(e)
            assert "Validation error:" in result
            assert "x" in result

    def test_missing_field(self) -> None:
        class _M(BaseModel):
            a: str
            b: int

        try:
            _M.model_validate({})
        except ValidationError as e:
            result = prettify_validation_error(e)
            assert "a" in result
            assert "b" in result

    def test_root_level_error(self) -> None:
        """Errors with empty loc should show 'root'."""

        class _M(BaseModel):
            x: int

        try:
            _M.model_validate("not_a_dict")
        except ValidationError as e:
            result = prettify_validation_error(e)
            assert "root" in result


class TestGetTradingCompetitionSubaccountAddr:
    def test_returns_deterministic_address(self) -> None:
        addr = "0x1"
        result = get_trading_competition_subaccount_addr(addr)
        assert isinstance(result, str)
        assert result.startswith("0x")
        # Deterministic: same input -> same output
        assert get_trading_competition_subaccount_addr(addr) == result

    def test_different_addresses_differ(self) -> None:
        a = get_trading_competition_subaccount_addr("0x1")
        b = get_trading_competition_subaccount_addr("0x2")
        assert a != b


class TestGetVaultShareAddress:
    _VAULT_A = "0x" + "a" * 64
    _VAULT_B = "0x" + "b" * 64

    def test_returns_deterministic_address(self) -> None:
        result = get_vault_share_address(self._VAULT_A)
        assert isinstance(result, str)
        assert result.startswith("0x")
        assert get_vault_share_address(self._VAULT_A) == result

    def test_different_vaults_differ(self) -> None:
        a = get_vault_share_address(self._VAULT_A)
        b = get_vault_share_address(self._VAULT_B)
        assert a != b


class TestExtractVaultAddressFromCreateTx:
    def test_string_vault_address(self) -> None:
        tx: dict[str, Any] = {
            "events": [
                {
                    "type": "0x1::vault::VaultCreatedEvent",
                    "data": {"vault": "0xdeadbeef"},
                }
            ]
        }
        assert extract_vault_address_from_create_tx(tx) == "0xdeadbeef"

    def test_dict_vault_with_inner(self) -> None:
        tx: dict[str, Any] = {
            "events": [
                {
                    "type": "0x1::vault::VaultCreatedEvent",
                    "data": {"vault": {"inner": "0xcafe"}},
                }
            ]
        }
        assert extract_vault_address_from_create_tx(tx) == "0xcafe"

    def test_missing_events_raises(self) -> None:
        with pytest.raises(ValueError, match="Unable to extract"):
            extract_vault_address_from_create_tx({})

    def test_no_matching_event_raises(self) -> None:
        tx: dict[str, Any] = {"events": [{"type": "0x1::other::Event", "data": {}}]}
        with pytest.raises(ValueError, match="Unable to extract"):
            extract_vault_address_from_create_tx(tx)

    def test_events_not_list_raises(self) -> None:
        with pytest.raises(ValueError, match="Unable to extract"):
            extract_vault_address_from_create_tx({"events": "not_a_list"})


class TestFetchError:
    def test_json_response_data(self) -> None:
        data = json.dumps({"status": "error", "message": "not found"})
        err = FetchError(data, 404, "Not Found")
        assert err.status == 404
        assert err.status_text == "error"
        assert err.response_message == "not found"
        assert "404" in str(err)

    def test_non_json_response_data(self) -> None:
        err = FetchError("plain text body", 500, "Server Error")
        assert err.status == 500
        assert err.status_text == "Server Error"
        assert err.response_message == "plain text body"

    def test_json_without_status_and_message(self) -> None:
        data = json.dumps({"foo": "bar"})
        err = FetchError(data, 400, "Bad Request")
        assert err.status_text == "Bad Request"
        assert err.response_message == data

    def test_empty_status_text(self) -> None:
        data = json.dumps({"status": "err", "message": "oops"})
        err = FetchError(data, 422, "")
        assert err.status_text == "err"


# ===================================================================
# 4b. Sync request wrappers (get/post/patch)
# ===================================================================


class TestSyncRequestWrappers:
    def test_get_request_sync_success(self) -> None:
        transport = SyncMockTransport()
        transport.set_response({"value": "ok"})
        client = httpx.Client(transport=transport)

        data, status, status_text = get_request_sync(
            _DummyModel,
            "http://test/api",
            params={"q": "1"},
            client=client,
        )
        assert isinstance(data, _DummyModel)
        assert data.value == "ok"
        assert status == 200
        req = transport.captured_requests[0]
        assert req.method == "GET"
        assert "q=1" in req.url

    def test_get_request_sync_with_api_key(self) -> None:
        transport = SyncMockTransport()
        transport.set_response({"value": "ok"})
        client = httpx.Client(transport=transport)

        get_request_sync(
            _DummyModel,
            "http://test/api",
            api_key="secret",
            client=client,
        )
        req = transport.captured_requests[0]
        assert req.headers.get("authorization") == "Bearer secret"

    def test_post_request_sync_success(self) -> None:
        transport = SyncMockTransport()
        transport.set_response({"value": "created"})
        client = httpx.Client(transport=transport)

        data, status, _ = post_request_sync(
            _DummyModel,
            "http://test/api",
            body={"key": "val"},
            client=client,
        )
        assert data.value == "created"
        assert status == 200
        req = transport.captured_requests[0]
        assert req.method == "POST"
        assert "application/json" in req.headers.get("content-type", "")

    def test_patch_request_sync_success(self) -> None:
        transport = SyncMockTransport()
        transport.set_response({"value": "patched"})
        client = httpx.Client(transport=transport)

        data, _, _ = patch_request_sync(
            _DummyModel,
            "http://test/api",
            body={"key": "val"},
            client=client,
        )
        assert data.value == "patched"
        req = transport.captured_requests[0]
        assert req.method == "PATCH"

    def test_get_request_sync_http_error(self) -> None:
        transport = SyncMockTransport()
        transport.set_response(
            {"status": "error", "message": "bad"},
            status_code=400,
        )
        client = httpx.Client(transport=transport)

        with pytest.raises(FetchError) as exc_info:
            get_request_sync(
                _DummyModel,
                "http://test/api",
                client=client,
            )
        assert exc_info.value.status == 400

    def test_post_request_sync_validation_error(self) -> None:
        transport = SyncMockTransport()
        # Return data that does not match _DummyModel
        transport.set_response({"wrong_field": 123})
        client = httpx.Client(transport=transport)

        with pytest.raises(ValueError, match="Validation error"):
            post_request_sync(
                _DummyModel,
                "http://test/api",
                body={},
                client=client,
            )


# ===================================================================
# 5. _gas_price_manager._build_auth_headers
# ===================================================================


class TestBuildAuthHeaders:
    def test_with_api_key(self) -> None:
        headers = _build_auth_headers("my-key")
        assert headers == {"x-api-key": "my-key"}

    def test_without_api_key(self) -> None:
        assert _build_auth_headers(None) == {}

    def test_empty_string_api_key(self) -> None:
        assert _build_auth_headers("") == {}
