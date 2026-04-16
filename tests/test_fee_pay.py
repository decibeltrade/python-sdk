"""Unit tests for decibel._fee_pay module.

Covers: submit_fee_paid_transaction, submit_fee_paid_transaction_sync,
_submit_via_gas_station_api, _submit_via_gas_station_api_sync,
_submit_via_legacy_fee_payer, _submit_via_legacy_fee_payer_sync,
_get_default_gas_station_url.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel._constants import DecibelConfig, Network
from decibel._fee_pay import (
    PendingTransactionResponse,
    _get_default_gas_station_url,
    _submit_via_gas_station_api,
    _submit_via_gas_station_api_sync,
    _submit_via_legacy_fee_payer,
    _submit_via_legacy_fee_payer_sync,
    submit_fee_paid_transaction,
    submit_fee_paid_transaction_sync,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_httpx_response(
    status_code: int = 200,
    json_data: Any = None,
    text: str = "",
) -> httpx.Response:
    if json_data is not None:
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            request=httpx.Request("POST", "https://test.example.com"),
        )
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("POST", "https://test.example.com"),
    )


def _make_mock_transaction() -> MagicMock:
    """Build a SimpleTransaction-like mock with serialisable internals."""
    mock_transaction = MagicMock()
    mock_raw = MagicMock()
    mock_raw.sender = "0x" + "aa" * 32
    mock_raw.sequence_number = 1
    mock_raw.max_gas_amount = 200000
    mock_raw.gas_unit_price = 100
    mock_raw.expiration_timestamps_secs = 9999999999

    # serialize writes bytes into a Serializer — just let it be a no-op mock
    mock_raw.serialize = MagicMock()

    mock_transaction.raw_transaction = mock_raw
    mock_transaction.fee_payer_address = None
    return mock_transaction


def _make_mock_authenticator() -> MagicMock:
    """Build an AccountAuthenticator-like mock."""
    mock_auth = MagicMock()
    # serialize is called with a Serializer; make it a no-op
    mock_auth.serialize = MagicMock()
    return mock_auth


def _gas_api_config(test_config: DecibelConfig) -> DecibelConfig:
    return replace(test_config, gas_station_api_key="gs-api-key")


def _legacy_only_config(test_config: DecibelConfig) -> DecibelConfig:
    return replace(
        test_config,
        gas_station_api_key=None,
        gas_station_url="https://legacy-gas.example.com",
    )


def _no_gas_config(test_config: DecibelConfig) -> DecibelConfig:
    return replace(test_config, gas_station_api_key=None, gas_station_url=None)


# ---------------------------------------------------------------------------
# PendingTransactionResponse model
# ---------------------------------------------------------------------------


class TestPendingTransactionResponse:
    def test_creation(self) -> None:
        resp = PendingTransactionResponse(
            hash="0xabc",
            sender="0xsender",
            sequence_number="1",
            max_gas_amount="200000",
            gas_unit_price="100",
            expiration_timestamp_secs="9999999",
        )
        assert resp.hash == "0xabc"
        assert resp.sender == "0xsender"


# ---------------------------------------------------------------------------
# submit_fee_paid_transaction (async routing)
# ---------------------------------------------------------------------------


class TestSubmitFeePaidTransaction:
    @pytest.mark.asyncio
    async def test_routes_to_gas_station_api_when_api_key_present(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()
        expected = PendingTransactionResponse(
            hash="0xhash1",
            sender="0xsender",
            sequence_number="1",
            max_gas_amount="200000",
            gas_unit_price="100",
            expiration_timestamp_secs="9999",
        )

        with patch(
            "decibel._fee_pay._submit_via_gas_station_api",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_fn:
            result = await submit_fee_paid_transaction(config, mock_txn, mock_auth)

        assert result is expected
        mock_fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routes_to_legacy_when_only_gas_station_url(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()
        expected = PendingTransactionResponse(
            hash="0xhash2",
            sender="0xsender",
            sequence_number="1",
            max_gas_amount="200000",
            gas_unit_price="100",
            expiration_timestamp_secs="9999",
        )

        with patch(
            "decibel._fee_pay._submit_via_legacy_fee_payer",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_fn:
            result = await submit_fee_paid_transaction(config, mock_txn, mock_auth)

        assert result is expected
        mock_fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_neither_key_nor_url(self, test_config: Any) -> None:
        config = _no_gas_config(test_config)
        with pytest.raises(ValueError, match="gas_station_api_key or gas_station_url"):
            await submit_fee_paid_transaction(
                config, _make_mock_transaction(), _make_mock_authenticator()
            )


# ---------------------------------------------------------------------------
# submit_fee_paid_transaction_sync (sync routing)
# ---------------------------------------------------------------------------


class TestSubmitFeePaidTransactionSync:
    def test_routes_to_gas_station_api_when_api_key_present(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()
        expected = PendingTransactionResponse(
            hash="0xhash3",
            sender="0xsender",
            sequence_number="1",
            max_gas_amount="200000",
            gas_unit_price="100",
            expiration_timestamp_secs="9999",
        )

        with patch(
            "decibel._fee_pay._submit_via_gas_station_api_sync",
            return_value=expected,
        ) as mock_fn:
            result = submit_fee_paid_transaction_sync(config, mock_txn, mock_auth)

        assert result is expected
        mock_fn.assert_called_once()

    def test_routes_to_legacy_when_only_gas_station_url(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()
        expected = PendingTransactionResponse(
            hash="0xhash4",
            sender="0xsender",
            sequence_number="1",
            max_gas_amount="200000",
            gas_unit_price="100",
            expiration_timestamp_secs="9999",
        )

        with patch(
            "decibel._fee_pay._submit_via_legacy_fee_payer_sync",
            return_value=expected,
        ) as mock_fn:
            result = submit_fee_paid_transaction_sync(config, mock_txn, mock_auth)

        assert result is expected
        mock_fn.assert_called_once()

    def test_raises_when_neither_key_nor_url(self, test_config: Any) -> None:
        config = _no_gas_config(test_config)
        with pytest.raises(ValueError, match="gas_station_api_key or gas_station_url"):
            submit_fee_paid_transaction_sync(
                config, _make_mock_transaction(), _make_mock_authenticator()
            )


# ---------------------------------------------------------------------------
# _submit_via_gas_station_api (async)
# ---------------------------------------------------------------------------


class TestSubmitViaGasStationApi:
    @pytest.mark.asyncio
    async def test_success_with_provided_client(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {"transactionHash": "0xgas_station_hash"}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        result = await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=mock_client)

        assert result.hash == "0xgas_station_hash"
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_uses_hash_fallback(self, test_config: Any) -> None:
        """When 'transactionHash' absent, falls back to 'hash'."""
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {"hash": "0xfallback_hash"}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        result = await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=mock_client)
        assert result.hash == "0xfallback_hash"

    @pytest.mark.asyncio
    async def test_error_raises_value_error(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=_make_httpx_response(400, text="Bad Request"))

        with pytest.raises(ValueError, match="Gas station API error"):
            await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=mock_client)

    @pytest.mark.asyncio
    async def test_without_client_creates_temp_client(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {"transactionHash": "0xtemp"}
        mock_temp = AsyncMock(spec=httpx.AsyncClient)
        mock_temp.post = AsyncMock(return_value=_make_httpx_response(200, json_data=response_data))
        mock_temp.__aenter__ = AsyncMock(return_value=mock_temp)
        mock_temp.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_temp):
            result = await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=None)

        assert result.hash == "0xtemp"

    @pytest.mark.asyncio
    async def test_sends_authorization_header(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"transactionHash": "0xok"})
        )

        await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=mock_client)

        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == f"Bearer {config.gas_station_api_key}"

    @pytest.mark.asyncio
    async def test_with_fee_payer_address_serialised(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        # Simulate a fee_payer_address being set
        mock_fee_payer_addr = MagicMock()
        mock_fee_payer_addr.serialize = MagicMock()
        mock_txn.fee_payer_address = mock_fee_payer_addr
        mock_auth = _make_mock_authenticator()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"transactionHash": "0xfp"})
        )

        result = await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=mock_client)
        assert result.hash == "0xfp"
        mock_fee_payer_addr.serialize.assert_called()

    @pytest.mark.asyncio
    async def test_response_has_correct_sender_fields(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"transactionHash": "0xh"})
        )

        result = await _submit_via_gas_station_api(config, mock_txn, mock_auth, client=mock_client)

        assert result.sequence_number == str(mock_txn.raw_transaction.sequence_number)
        assert result.max_gas_amount == str(mock_txn.raw_transaction.max_gas_amount)
        assert result.gas_unit_price == str(mock_txn.raw_transaction.gas_unit_price)


# ---------------------------------------------------------------------------
# _submit_via_gas_station_api_sync
# ---------------------------------------------------------------------------


class TestSubmitViaGasStationApiSync:
    def test_success_with_provided_client(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {"transactionHash": "0xsync_gs_hash"}
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        result = _submit_via_gas_station_api_sync(config, mock_txn, mock_auth, client=mock_client)
        assert result.hash == "0xsync_gs_hash"

    def test_success_hash_fallback(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data={"hash": "0xsync_fallback"})
        )

        result = _submit_via_gas_station_api_sync(config, mock_txn, mock_auth, client=mock_client)
        assert result.hash == "0xsync_fallback"

    def test_error_raises_value_error(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(500, text="Internal Server Error")
        )

        with pytest.raises(ValueError, match="Gas station API error"):
            _submit_via_gas_station_api_sync(config, mock_txn, mock_auth, client=mock_client)

    def test_without_client_creates_temp_client(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {"transactionHash": "0xsync_temp"}
        mock_temp = MagicMock(spec=httpx.Client)
        mock_temp.post = MagicMock(return_value=_make_httpx_response(200, json_data=response_data))
        mock_temp.__enter__ = MagicMock(return_value=mock_temp)
        mock_temp.__exit__ = MagicMock(return_value=None)

        with patch("httpx.Client", return_value=mock_temp):
            result = _submit_via_gas_station_api_sync(config, mock_txn, mock_auth, client=None)

        assert result.hash == "0xsync_temp"

    def test_sends_authorization_header(self, test_config: Any) -> None:
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data={"transactionHash": "0xok"})
        )

        _submit_via_gas_station_api_sync(config, mock_txn, mock_auth, client=mock_client)

        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == f"Bearer {config.gas_station_api_key}"

    def test_with_fee_payer_address_serialised(self, test_config: Any) -> None:
        """Covers the fee_payer_address.serialize branch in _submit_via_gas_station_api_sync."""
        config = _gas_api_config(test_config)
        mock_txn = _make_mock_transaction()
        # Set a fee_payer_address that is not None
        mock_fee_payer_addr = MagicMock()
        mock_fee_payer_addr.serialize = MagicMock()
        mock_txn.fee_payer_address = mock_fee_payer_addr
        mock_auth = _make_mock_authenticator()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data={"transactionHash": "0xfp_sync"})
        )

        result = _submit_via_gas_station_api_sync(config, mock_txn, mock_auth, client=mock_client)
        assert result.hash == "0xfp_sync"
        mock_fee_payer_addr.serialize.assert_called()


# ---------------------------------------------------------------------------
# _submit_via_legacy_fee_payer (async)
# ---------------------------------------------------------------------------


class TestSubmitViaLegacyFeePayer:
    @pytest.mark.asyncio
    async def test_success_with_provided_client(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {
            "hash": "0xlegacy_hash",
            "sender": "0xsender",
            "sequence_number": "1",
            "max_gas_amount": "200000",
            "gas_unit_price": "100",
            "expiration_timestamp_secs": "9999",
        }
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        result = await _submit_via_legacy_fee_payer(config, mock_txn, mock_auth, client=mock_client)

        assert result.hash == "0xlegacy_hash"
        assert result.sender == "0xsender"

    @pytest.mark.asyncio
    async def test_error_raises_value_error(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=_make_httpx_response(400, text="Bad request"))

        with pytest.raises(ValueError, match="Fee payer error"):
            await _submit_via_legacy_fee_payer(config, mock_txn, mock_auth, client=mock_client)

    @pytest.mark.asyncio
    async def test_without_client_creates_temp_client(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {
            "hash": "0xtemp_legacy",
            "sender": "0xsender",
            "sequence_number": "1",
            "max_gas_amount": "200000",
            "gas_unit_price": "100",
            "expiration_timestamp_secs": "9999",
        }
        mock_temp = AsyncMock(spec=httpx.AsyncClient)
        mock_temp.post = AsyncMock(return_value=_make_httpx_response(200, json_data=response_data))
        mock_temp.__aenter__ = AsyncMock(return_value=mock_temp)
        mock_temp.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_temp):
            result = await _submit_via_legacy_fee_payer(config, mock_txn, mock_auth, client=None)

        assert result.hash == "0xtemp_legacy"

    @pytest.mark.asyncio
    async def test_posts_to_correct_url(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {
            "hash": "0xurl_check",
            "sender": "",
            "sequence_number": "",
            "max_gas_amount": "",
            "gas_unit_price": "",
            "expiration_timestamp_secs": "",
        }
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        await _submit_via_legacy_fee_payer(config, mock_txn, mock_auth, client=mock_client)

        call_args = mock_client.post.call_args
        assert call_args.args[0] == f"{config.gas_station_url}/transactions"


# ---------------------------------------------------------------------------
# _submit_via_legacy_fee_payer_sync
# ---------------------------------------------------------------------------


class TestSubmitViaLegacyFeePayerSync:
    def test_success_with_provided_client(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {
            "hash": "0xsync_legacy",
            "sender": "0xsender",
            "sequence_number": "1",
            "max_gas_amount": "200000",
            "gas_unit_price": "100",
            "expiration_timestamp_secs": "9999",
        }
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        result = _submit_via_legacy_fee_payer_sync(config, mock_txn, mock_auth, client=mock_client)
        assert result.hash == "0xsync_legacy"

    def test_error_raises_value_error(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(return_value=_make_httpx_response(500, text="Server Error"))

        with pytest.raises(ValueError, match="Fee payer error"):
            _submit_via_legacy_fee_payer_sync(config, mock_txn, mock_auth, client=mock_client)

    def test_without_client_creates_temp_client(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {
            "hash": "0xsync_temp_legacy",
            "sender": "",
            "sequence_number": "",
            "max_gas_amount": "",
            "gas_unit_price": "",
            "expiration_timestamp_secs": "",
        }
        mock_temp = MagicMock(spec=httpx.Client)
        mock_temp.post = MagicMock(return_value=_make_httpx_response(200, json_data=response_data))
        mock_temp.__enter__ = MagicMock(return_value=mock_temp)
        mock_temp.__exit__ = MagicMock(return_value=None)

        with patch("httpx.Client", return_value=mock_temp):
            result = _submit_via_legacy_fee_payer_sync(config, mock_txn, mock_auth, client=None)

        assert result.hash == "0xsync_temp_legacy"

    def test_posts_to_correct_url(self, test_config: Any) -> None:
        config = _legacy_only_config(test_config)
        mock_txn = _make_mock_transaction()
        mock_auth = _make_mock_authenticator()

        response_data = {
            "hash": "0x",
            "sender": "",
            "sequence_number": "",
            "max_gas_amount": "",
            "gas_unit_price": "",
            "expiration_timestamp_secs": "",
        }
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data=response_data)
        )

        _submit_via_legacy_fee_payer_sync(config, mock_txn, mock_auth, client=mock_client)

        call_args = mock_client.post.call_args
        assert call_args.args[0] == f"{config.gas_station_url}/transactions"


# ---------------------------------------------------------------------------
# _get_default_gas_station_url
# ---------------------------------------------------------------------------


class TestGetDefaultGasStationUrl:
    def test_testnet_returns_testnet_url(self, test_config: Any) -> None:
        config = replace(test_config, network=Network.TESTNET)
        url = _get_default_gas_station_url(config)
        assert "testnet" in url
        assert "aptoslabs" in url

    def test_custom_network_with_gas_station_url_returns_it(self, test_config: Any) -> None:
        custom_url = "https://my-custom-gas-station.example.com/v1"
        config = replace(
            test_config,
            network=Network.CUSTOM,
            chain_id=999,
            gas_station_url=custom_url,
        )
        url = _get_default_gas_station_url(config)
        assert url == custom_url

    def test_custom_network_without_gas_station_url_raises(self, test_config: Any) -> None:
        config = replace(
            test_config,
            network=Network.CUSTOM,
            chain_id=999,
            gas_station_url=None,
        )
        with pytest.raises(ValueError, match="gas_station_url must be provided"):
            _get_default_gas_station_url(config)

    def test_mainnet_without_gas_station_url_raises(self, test_config: Any) -> None:
        config = replace(
            test_config,
            network=Network.MAINNET,
            chain_id=1,
            gas_station_url=None,
        )
        # MAINNET is not explicitly handled, falls through to gas_station_url check
        with pytest.raises(ValueError, match="gas_station_url must be provided"):
            _get_default_gas_station_url(config)

    def test_mainnet_with_gas_station_url_returns_it(self, test_config: Any) -> None:
        mainnet_gs_url = "https://api.mainnet.aptoslabs.com/gs/v1"
        config = replace(
            test_config,
            network=Network.MAINNET,
            chain_id=1,
            gas_station_url=mainnet_gs_url,
        )
        url = _get_default_gas_station_url(config)
        assert url == mainnet_gs_url
