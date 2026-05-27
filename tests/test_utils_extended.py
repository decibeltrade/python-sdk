"""Extended unit tests for decibel._utils module.

Covers: FetchError, bigint_reviver, prettify_validation_error,
_base_request_async, _base_request_sync, _process_response,
address derivation helpers, extract_vault_address_from_create_tx,
generate_random_replay_protection_nonce.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from decibel._utils import (
    FetchError,
    _base_request_async,
    _base_request_sync,
    _process_response,
    bigint_reviver,
    extract_vault_address_from_create_tx,
    generate_random_replay_protection_nonce,
    get_market_addr,
    get_primary_subaccount_addr,
    get_request,
    get_request_sync,
    get_trading_competition_subaccount_addr,
    get_vault_share_address,
    patch_request,
    patch_request_sync,
    post_request,
    post_request_sync,
    prettify_validation_error,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SimpleModel(BaseModel):
    value: int
    name: str


def _make_response(
    status_code: int = 200,
    json_data: Any = None,
    text: str = "",
) -> httpx.Response:
    if json_data is not None:
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            request=httpx.Request("GET", "https://test.example.com"),
        )
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("GET", "https://test.example.com"),
    )


# ---------------------------------------------------------------------------
# FetchError
# ---------------------------------------------------------------------------


class TestFetchError:
    def test_json_response_with_status_and_message(self) -> None:
        body = json.dumps({"status": "NOT_FOUND", "message": "Resource missing"})
        err = FetchError(body, 404, "Not Found")

        assert err.status == 404
        assert err.status_text == "NOT_FOUND"
        assert err.response_message == "Resource missing"
        assert "404" in str(err)
        assert "NOT_FOUND" in str(err)
        assert "Resource missing" in str(err)

    def test_json_response_missing_status_and_message_fields(self) -> None:
        body = json.dumps({"foo": "bar"})
        err = FetchError(body, 500, "Server Error")

        # Falls back to HTTP status_text and raw body
        assert err.status == 500
        assert err.status_text == "Server Error"
        assert err.response_message == body

    def test_json_response_non_string_status(self) -> None:
        body = json.dumps({"status": 42, "message": "hello"})
        err = FetchError(body, 400, "Bad Request")

        # status is int, not str → should fall back
        assert err.status_text == "Bad Request"
        # message is str → should be used
        assert err.response_message == "hello"

    def test_non_json_response(self) -> None:
        body = "plain text error"
        err = FetchError(body, 503, "Service Unavailable")

        assert err.status == 503
        assert err.status_text == "Service Unavailable"
        assert err.response_message == "plain text error"

    def test_empty_response(self) -> None:
        err = FetchError("", 422, "Unprocessable Entity")
        assert err.status == 422
        assert err.status_text == "Unprocessable Entity"

    def test_is_exception(self) -> None:
        err = FetchError("{}", 400, "Bad Request")
        assert isinstance(err, Exception)

    def test_message_format_no_status_text(self) -> None:
        # When status_text is empty string, parenthetical should be omitted
        body = json.dumps({"status": "", "message": "oops"})
        err = FetchError(body, 400, "fallback")
        # status is empty str → falsy → should show fallback
        assert "400" in str(err)


# ---------------------------------------------------------------------------
# bigint_reviver
# ---------------------------------------------------------------------------


class TestBigintReviver:
    def test_converts_bigint_string_to_int(self) -> None:
        result = bigint_reviver({"$bigint": "123456789012345678"})
        assert result == 123456789012345678
        assert isinstance(result, int)

    def test_zero_bigint(self) -> None:
        assert bigint_reviver({"$bigint": "0"}) == 0

    def test_passes_through_normal_dict(self) -> None:
        d = {"a": 1, "b": "hello"}
        assert bigint_reviver(d) is d

    def test_bigint_non_string_value_passes_through(self) -> None:
        # If $bigint is not a str, should pass through unchanged
        d = {"$bigint": 999}
        result = bigint_reviver(d)
        assert result is d

    def test_empty_dict(self) -> None:
        d: dict[str, Any] = {}
        result = bigint_reviver(d)
        assert result is d

    def test_dict_with_other_keys(self) -> None:
        d = {"name": "Alice", "age": 30}
        assert bigint_reviver(d) is d

    def test_json_loads_with_hook(self) -> None:
        payload = '{"amount": {"$bigint": "99999999999999"}}'
        result = json.loads(payload, object_hook=bigint_reviver)
        assert result["amount"] == 99999999999999


# ---------------------------------------------------------------------------
# prettify_validation_error
# ---------------------------------------------------------------------------


class TestPrettifyValidationError:
    def _make_validation_error(self) -> ValidationError:
        try:
            _SimpleModel.model_validate({"value": "not_an_int", "name": 123})
        except ValidationError as e:
            return e
        pytest.fail("Expected ValidationError not raised")

    def test_returns_string(self) -> None:
        err = self._make_validation_error()
        result = prettify_validation_error(err)
        assert isinstance(result, str)

    def test_starts_with_validation_error(self) -> None:
        err = self._make_validation_error()
        result = prettify_validation_error(err)
        assert result.startswith("Validation error:")

    def test_contains_field_location(self) -> None:
        err = self._make_validation_error()
        result = prettify_validation_error(err)
        # Should contain field name from error location
        assert "value" in result or "name" in result

    def test_missing_required_field(self) -> None:
        try:
            _SimpleModel.model_validate({})
        except ValidationError as e:
            result = prettify_validation_error(e)
            assert "Validation error:" in result
            assert "value" in result or "name" in result

    def test_root_location_fallback(self) -> None:
        """When loc is empty, should show 'root'."""
        mock_error = MagicMock()
        mock_error.errors.return_value = [{"loc": (), "msg": "some error"}]
        result = prettify_validation_error(mock_error)
        assert "root" in result
        assert "some error" in result


# ---------------------------------------------------------------------------
# _process_response
# ---------------------------------------------------------------------------


class TestProcessResponse:
    def test_success_with_valid_json(self) -> None:
        response = _make_response(200, json_data={"value": 42, "name": "test"})
        data, status, status_text = _process_response(_SimpleModel, response)
        assert data.value == 42
        assert data.name == "test"
        assert status == 200

    def test_non_success_raises_fetch_error(self) -> None:
        response = _make_response(404, text="Not found")
        with pytest.raises(FetchError) as exc_info:
            _process_response(_SimpleModel, response)
        assert exc_info.value.status == 404

    def test_server_error_raises_fetch_error(self) -> None:
        response = _make_response(500, text="Internal Server Error")
        with pytest.raises(FetchError):
            _process_response(_SimpleModel, response)

    def test_validation_error_raises_value_error(self) -> None:
        # Response is valid JSON but doesn't match model
        response = _make_response(200, json_data={"unexpected": "data"})
        with pytest.raises(ValueError, match="Validation error"):
            _process_response(_SimpleModel, response)

    def test_bigint_reviver_is_applied(self) -> None:
        class BigintModel(BaseModel):
            amount: int

        response = _make_response(200, text='{"amount": {"$bigint": "987"}}')
        data, _, _ = _process_response(BigintModel, response)
        assert data.amount == 987

    def test_returns_status_code_and_reason(self) -> None:
        response = _make_response(201, json_data={"value": 1, "name": "a"})
        _, status, _ = _process_response(_SimpleModel, response)
        assert status == 201


# ---------------------------------------------------------------------------
# _base_request_async
# ---------------------------------------------------------------------------


class TestBaseRequestAsync:
    @pytest.mark.asyncio
    async def test_get_with_provided_client(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 1, "name": "x"})
        )

        data, status, _ = await _base_request_async(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            client=mock_client,
        )

        mock_client.request.assert_awaited_once()
        call_kwargs = mock_client.request.call_args
        assert call_kwargs.kwargs["method"] == "GET"
        assert data.value == 1
        assert status == 200

    @pytest.mark.asyncio
    async def test_get_passes_params(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 2, "name": "y"})
        )

        await _base_request_async(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            params={"foo": "bar"},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["params"] == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_post_adds_content_type_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 3, "name": "z"})
        )

        await _base_request_async(
            _SimpleModel,
            "https://example.com/api",
            "POST",
            body={"key": "val"},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_patch_adds_content_type_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 4, "name": "w"})
        )

        await _base_request_async(
            _SimpleModel,
            "https://example.com/api",
            "PATCH",
            body={"key": "val"},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_api_key_adds_authorization_header(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 5, "name": "v"})
        )

        await _base_request_async(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            api_key="secret-key",
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer secret-key"

    @pytest.mark.asyncio
    async def test_error_response_raises_fetch_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(return_value=_make_response(401, text="Unauthorized"))

        with pytest.raises(FetchError) as exc_info:
            await _base_request_async(
                _SimpleModel,
                "https://example.com/api",
                "GET",
                client=mock_client,
            )
        assert exc_info.value.status == 401

    @pytest.mark.asyncio
    async def test_without_client_creates_temp_client(self) -> None:
        mock_response = _make_response(200, json_data={"value": 6, "name": "u"})
        mock_temp = AsyncMock(spec=httpx.AsyncClient)
        mock_temp.request = AsyncMock(return_value=mock_response)
        mock_temp.__aenter__ = AsyncMock(return_value=mock_temp)
        mock_temp.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_temp):
            data, _, _ = await _base_request_async(
                _SimpleModel,
                "https://example.com/api",
                "GET",
            )
        assert data.value == 6

    @pytest.mark.asyncio
    async def test_get_does_not_send_body(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 7, "name": "t"})
        )

        await _base_request_async(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            body={"should_be_ignored": True},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["json"] is None


# ---------------------------------------------------------------------------
# _base_request_sync
# ---------------------------------------------------------------------------


class TestBaseRequestSync:
    def test_get_with_provided_client(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 10, "name": "sync"})
        )

        data, status, _ = _base_request_sync(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            client=mock_client,
        )

        mock_client.request.assert_called_once()
        assert data.value == 10
        assert status == 200

    def test_post_adds_content_type_header(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 11, "name": "s"})
        )

        _base_request_sync(
            _SimpleModel,
            "https://example.com/api",
            "POST",
            body={"k": "v"},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

    def test_patch_adds_content_type_header(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 12, "name": "r"})
        )

        _base_request_sync(
            _SimpleModel,
            "https://example.com/api",
            "PATCH",
            body={"k": "v"},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["headers"]["Content-Type"] == "application/json"

    def test_api_key_adds_authorization_header(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 13, "name": "q"})
        )

        _base_request_sync(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            api_key="my-key",
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-key"

    def test_error_response_raises_fetch_error(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(return_value=_make_response(403, text="Forbidden"))

        with pytest.raises(FetchError) as exc_info:
            _base_request_sync(
                _SimpleModel,
                "https://example.com/api",
                "GET",
                client=mock_client,
            )
        assert exc_info.value.status == 403

    def test_without_client_creates_temp_client(self) -> None:
        mock_response = _make_response(200, json_data={"value": 14, "name": "p"})
        mock_temp = MagicMock(spec=httpx.Client)
        mock_temp.request = MagicMock(return_value=mock_response)
        mock_temp.__enter__ = MagicMock(return_value=mock_temp)
        mock_temp.__exit__ = MagicMock(return_value=None)

        with patch("httpx.Client", return_value=mock_temp):
            data, _, _ = _base_request_sync(
                _SimpleModel,
                "https://example.com/api",
                "GET",
            )
        assert data.value == 14

    def test_params_passed_correctly(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 15, "name": "o"})
        )

        _base_request_sync(
            _SimpleModel,
            "https://example.com/api",
            "GET",
            params={"limit": "10"},
            client=mock_client,
        )

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["params"] == {"limit": "10"}


# ---------------------------------------------------------------------------
# Address derivation helpers (pure functions using real aptos_sdk)
# ---------------------------------------------------------------------------


TEST_PACKAGE = "0x" + "ab" * 32
TEST_PERP_ENGINE = "0x" + "12" * 32
TEST_ADDR = "0x" + "aa" * 32


class TestGetMarketAddr:
    def test_returns_string(self) -> None:
        result = get_market_addr("BTC-PERP", TEST_PERP_ENGINE)
        assert isinstance(result, str)
        assert result.startswith("0x")

    def test_different_market_names_give_different_addresses(self) -> None:
        addr1 = get_market_addr("BTC-PERP", TEST_PERP_ENGINE)
        addr2 = get_market_addr("ETH-PERP", TEST_PERP_ENGINE)
        assert addr1 != addr2

    def test_same_inputs_give_same_address(self) -> None:
        addr1 = get_market_addr("BTC-PERP", TEST_PERP_ENGINE)
        addr2 = get_market_addr("BTC-PERP", TEST_PERP_ENGINE)
        assert addr1 == addr2

    def test_different_perp_engines_give_different_addresses(self) -> None:
        engine2 = "0x" + "34" * 32
        addr1 = get_market_addr("BTC-PERP", TEST_PERP_ENGINE)
        addr2 = get_market_addr("BTC-PERP", engine2)
        assert addr1 != addr2


class TestGetPrimarySubaccountAddr:
    def test_returns_string(self) -> None:
        from decibel._constants import CompatVersion

        result = get_primary_subaccount_addr(TEST_ADDR, CompatVersion.V0_4, TEST_PACKAGE)
        assert isinstance(result, str)
        assert result.startswith("0x")

    def test_deterministic(self) -> None:
        from decibel._constants import CompatVersion

        addr1 = get_primary_subaccount_addr(TEST_ADDR, CompatVersion.V0_4, TEST_PACKAGE)
        addr2 = get_primary_subaccount_addr(TEST_ADDR, CompatVersion.V0_4, TEST_PACKAGE)
        assert addr1 == addr2

    def test_different_owners_give_different_addresses(self) -> None:
        from decibel._constants import CompatVersion

        addr2 = "0x" + "bb" * 32
        result1 = get_primary_subaccount_addr(TEST_ADDR, CompatVersion.V0_4, TEST_PACKAGE)
        result2 = get_primary_subaccount_addr(addr2, CompatVersion.V0_4, TEST_PACKAGE)
        assert result1 != result2

    def test_accepts_account_address_object(self) -> None:
        from aptos_sdk.account_address import AccountAddress

        from decibel._constants import CompatVersion

        addr_obj = AccountAddress.from_str(TEST_ADDR)
        result = get_primary_subaccount_addr(addr_obj, CompatVersion.V0_4, TEST_PACKAGE)
        assert isinstance(result, str)


class TestGetTradingCompetitionSubaccountAddr:
    def test_returns_string(self) -> None:
        result = get_trading_competition_subaccount_addr(TEST_ADDR)
        assert isinstance(result, str)
        assert result.startswith("0x")

    def test_deterministic(self) -> None:
        r1 = get_trading_competition_subaccount_addr(TEST_ADDR)
        r2 = get_trading_competition_subaccount_addr(TEST_ADDR)
        assert r1 == r2

    def test_different_accounts_give_different_addresses(self) -> None:
        addr2 = "0x" + "cc" * 32
        r1 = get_trading_competition_subaccount_addr(TEST_ADDR)
        r2 = get_trading_competition_subaccount_addr(addr2)
        assert r1 != r2

    def test_accepts_account_address_object(self) -> None:
        from aptos_sdk.account_address import AccountAddress

        addr_obj = AccountAddress.from_str(TEST_ADDR)
        result = get_trading_competition_subaccount_addr(addr_obj)
        assert isinstance(result, str)


class TestGetVaultShareAddress:
    def test_returns_string(self) -> None:
        result = get_vault_share_address(TEST_ADDR)
        assert isinstance(result, str)
        assert result.startswith("0x")

    def test_deterministic(self) -> None:
        r1 = get_vault_share_address(TEST_ADDR)
        r2 = get_vault_share_address(TEST_ADDR)
        assert r1 == r2

    def test_different_vault_addresses_give_different_shares(self) -> None:
        vault2 = "0x" + "dd" * 32
        r1 = get_vault_share_address(TEST_ADDR)
        r2 = get_vault_share_address(vault2)
        assert r1 != r2


# ---------------------------------------------------------------------------
# extract_vault_address_from_create_tx
# ---------------------------------------------------------------------------


class TestExtractVaultAddressFromCreateTx:
    def _make_tx(self, vault_val: Any) -> dict[str, Any]:
        return {
            "events": [
                {
                    "type": "0xdeadbeef::vault::VaultCreatedEvent",
                    "data": {"vault": vault_val},
                }
            ]
        }

    def test_vault_as_string(self) -> None:
        tx = self._make_tx("0xabcdef")
        result = extract_vault_address_from_create_tx(tx)
        assert result == "0xabcdef"

    def test_vault_as_dict_with_inner(self) -> None:
        tx = self._make_tx({"inner": "0x123456"})
        result = extract_vault_address_from_create_tx(tx)
        assert result == "0x123456"

    def test_no_vault_created_event_raises(self) -> None:
        tx: dict[str, Any] = {
            "events": [
                {
                    "type": "0xdeadbeef::other::OtherEvent",
                    "data": {"foo": "bar"},
                }
            ]
        }
        with pytest.raises(ValueError, match="Unable to extract vault address"):
            extract_vault_address_from_create_tx(tx)

    def test_empty_events_raises(self) -> None:
        tx: dict[str, Any] = {"events": []}
        with pytest.raises(ValueError, match="Unable to extract vault address"):
            extract_vault_address_from_create_tx(tx)

    def test_no_events_key_raises(self) -> None:
        tx: dict[str, Any] = {}
        with pytest.raises(ValueError, match="Unable to extract vault address"):
            extract_vault_address_from_create_tx(tx)

    def test_vault_dict_without_inner_raises(self) -> None:
        # Dict vault but no "inner" key → should raise
        tx = self._make_tx({"other_key": "0xdeadbeef"})
        with pytest.raises(ValueError, match="Unable to extract vault address"):
            extract_vault_address_from_create_tx(tx)

    def test_vault_none_skipped_raises(self) -> None:
        tx: dict[str, Any] = {
            "events": [
                {
                    "type": "0xdeadbeef::vault::VaultCreatedEvent",
                    "data": {"vault": None},
                }
            ]
        }
        with pytest.raises(ValueError, match="Unable to extract vault address"):
            extract_vault_address_from_create_tx(tx)

    def test_stops_at_first_vault_event(self) -> None:
        tx: dict[str, Any] = {
            "events": [
                {
                    "type": "0xdeadbeef::vault::VaultCreatedEvent",
                    "data": {"vault": "0xfirst"},
                },
                {
                    "type": "0xdeadbeef::vault::VaultCreatedEvent",
                    "data": {"vault": "0xsecond"},
                },
            ]
        }
        result = extract_vault_address_from_create_tx(tx)
        assert result == "0xfirst"


# ---------------------------------------------------------------------------
# generate_random_replay_protection_nonce
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public request wrapper functions (get_request, post_request, etc.)
# ---------------------------------------------------------------------------


class TestPublicRequestWrappers:
    """Cover the thin wrapper functions that delegate to _base_request_async/sync."""

    @pytest.mark.asyncio
    async def test_get_request_delegates(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 1, "name": "a"})
        )
        data, status, _ = await get_request(
            _SimpleModel, "https://example.com/api", client=mock_client
        )
        assert data.value == 1
        assert status == 200

    @pytest.mark.asyncio
    async def test_post_request_delegates(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 2, "name": "b"})
        )
        data, _, _ = await post_request(
            _SimpleModel, "https://example.com/api", body={"x": 1}, client=mock_client
        )
        assert data.value == 2

    @pytest.mark.asyncio
    async def test_patch_request_delegates(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request = AsyncMock(
            return_value=_make_response(200, json_data={"value": 3, "name": "c"})
        )
        data, _, _ = await patch_request(
            _SimpleModel, "https://example.com/api", body={"y": 2}, client=mock_client
        )
        assert data.value == 3

    def test_get_request_sync_delegates(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 4, "name": "d"})
        )
        data, status, _ = get_request_sync(
            _SimpleModel, "https://example.com/api", client=mock_client
        )
        assert data.value == 4
        assert status == 200

    def test_post_request_sync_delegates(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 5, "name": "e"})
        )
        data, _, _ = post_request_sync(
            _SimpleModel, "https://example.com/api", body={"z": 3}, client=mock_client
        )
        assert data.value == 5

    def test_patch_request_sync_delegates(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request = MagicMock(
            return_value=_make_response(200, json_data={"value": 6, "name": "f"})
        )
        data, _, _ = patch_request_sync(
            _SimpleModel, "https://example.com/api", body={"w": 4}, client=mock_client
        )
        assert data.value == 6


class TestGenerateRandomReplayProtectionNonce:
    def test_returns_int_or_none(self) -> None:
        for _ in range(20):
            result = generate_random_replay_protection_nonce()
            assert result is None or isinstance(result, int)

    def test_non_none_result_is_positive(self) -> None:
        for _ in range(20):
            result = generate_random_replay_protection_nonce()
            if result is not None:
                assert result > 0

    def test_returns_none_when_buf_contains_zero(self) -> None:
        # When first buf element is 0, should return None
        with patch("secrets.randbits", side_effect=[0, 12345]):
            result = generate_random_replay_protection_nonce()
        assert result is None

    def test_returns_none_when_second_buf_is_zero(self) -> None:
        with patch("secrets.randbits", side_effect=[12345, 0]):
            result = generate_random_replay_protection_nonce()
        assert result is None

    def test_returns_combined_value_when_both_nonzero(self) -> None:
        buf0 = 0xDEAD
        buf1 = 0xBEEF
        with patch("secrets.randbits", side_effect=[buf0, buf1]):
            result = generate_random_replay_protection_nonce()
        expected = (buf0 << 32) | buf1
        assert result == expected

    def test_repeated_calls_return_int_when_randbits_is_nonzero(self) -> None:
        side_effect = list(range(1, 101))
        with patch("secrets.randbits", side_effect=side_effect):
            results = [generate_random_replay_protection_nonce() for _ in range(50)]
        assert all(isinstance(result, int) for result in results)
        assert all(result is not None for result in results)
