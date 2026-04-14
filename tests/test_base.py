"""Unit tests for decibel._base module.

Covers BaseSDK and BaseSDKSync: init, context managers, build_tx,
gas price fetching, simulation, signing, submit, wait for transaction,
and _send_tx full flow.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from decibel._base import (
    BaseSDK,
    BaseSDKOptions,
    BaseSDKOptionsSync,
    BaseSDKSync,
    _poll_delay,
)
from decibel._exceptions import TxnConfirmError, TxnSubmitError
from decibel._fee_pay import PendingTransactionResponse

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_pending_response(tx_hash: str = "0xdeadbeef") -> PendingTransactionResponse:
    return PendingTransactionResponse(
        hash=tx_hash,
        sender="0x" + "aa" * 32,
        sequence_number="1",
        max_gas_amount="200000",
        gas_unit_price="100",
        expiration_timestamp_secs="9999999999",
    )


def _make_httpx_response(
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


def _make_sdk(config: Any, account: Any, opts: Any = None) -> BaseSDK:
    with patch("decibel._base.AbiRegistry"), patch("decibel._base.RestClient"):
        sdk = BaseSDK(config=config, account=account, opts=opts)
    return sdk


def _make_sdk_sync(config: Any, account: Any, opts: Any = None) -> BaseSDKSync:
    with patch("decibel._base.AbiRegistry"):
        sdk = BaseSDKSync(config=config, account=account, opts=opts)
    return sdk


# ---------------------------------------------------------------------------
# _poll_delay helper
# ---------------------------------------------------------------------------


class TestPollDelay:
    def test_first_delay(self) -> None:
        assert _poll_delay(0) == pytest.approx(0.2)

    def test_second_delay(self) -> None:
        assert _poll_delay(1) == pytest.approx(0.2)

    def test_third_delay(self) -> None:
        assert _poll_delay(2) == pytest.approx(0.5)

    def test_fourth_delay(self) -> None:
        assert _poll_delay(3) == pytest.approx(0.5)

    def test_fifth_delay(self) -> None:
        assert _poll_delay(4) == pytest.approx(1.0)

    def test_beyond_table_returns_one(self) -> None:
        assert _poll_delay(5) == pytest.approx(1.0)
        assert _poll_delay(100) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# BaseSDK.__init__
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("test_config")
class TestBaseSDKInit:
    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_creates_http_client(self, mock_rest: Any, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        sdk = BaseSDK(config=test_config, account=account)
        assert isinstance(sdk._http_client, httpx.AsyncClient)
        assert sdk._config is test_config
        assert sdk._account is account

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_default_opts(self, mock_rest: Any, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        sdk = BaseSDK(config=test_config, account=account)
        assert sdk._skip_simulate is False
        assert sdk._no_fee_payer is False
        assert sdk._node_api_key is None
        assert sdk._gas_price_manager is None
        assert sdk._time_delta_ms == 0

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_custom_opts(self, mock_rest: Any, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        opts = BaseSDKOptions(
            skip_simulate=True,
            no_fee_payer=True,
            node_api_key="nodekey",
            time_delta_ms=500,
        )
        sdk = BaseSDK(config=test_config, account=account, opts=opts)
        assert sdk._skip_simulate is True
        assert sdk._no_fee_payer is True
        assert sdk._node_api_key == "nodekey"
        assert sdk._time_delta_ms == 500

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_none_chain_id_logs_warning(
        self, mock_rest: Any, mock_abi: Any, test_config: Any
    ) -> None:
        from dataclasses import replace

        config_no_chain = replace(test_config, chain_id=None)
        account = MagicMock()
        import logging

        with patch.object(logging.getLogger("decibel._base"), "warning") as mock_warn:
            BaseSDK(config=config_no_chain, account=account)
            mock_warn.assert_called_once()

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_creates_abi_registry_and_rest_client(
        self, mock_rest: Any, mock_abi: Any, test_config: Any
    ) -> None:
        account = MagicMock()
        BaseSDK(config=test_config, account=account)
        mock_abi.assert_called_once_with(chain_id=test_config.chain_id)
        mock_rest.assert_called_once_with(test_config.fullnode_url)

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_properties(self, mock_rest: Any, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        sdk = BaseSDK(config=test_config, account=account)
        assert sdk.config is test_config
        assert sdk.account is account
        assert sdk.skip_simulate is False
        assert sdk.no_fee_payer is False
        assert sdk.time_delta_ms == 0

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_time_delta_ms_setter(self, mock_rest: Any, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        sdk = BaseSDK(config=test_config, account=account)
        sdk.time_delta_ms = 1000
        assert sdk.time_delta_ms == 1000


# ---------------------------------------------------------------------------
# BaseSDK.close / context manager
# ---------------------------------------------------------------------------


class TestBaseSDKClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        await sdk.close()
        sdk._http_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        result = await sdk.__aenter__()
        assert result is sdk

    @pytest.mark.asyncio
    async def test_aexit_calls_close(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        await sdk.__aexit__(None, None, None)
        sdk._http_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        async with sdk as ctx:
            assert ctx is sdk
        sdk._http_client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# BaseSDK._fetch_gas_price_estimation
# ---------------------------------------------------------------------------


class TestBaseSDKFetchGasPrice:
    @pytest.mark.asyncio
    async def test_success(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"gas_estimate": 150})
        )

        price = await sdk._fetch_gas_price_estimation()
        assert price == 150

    @pytest.mark.asyncio
    async def test_uses_default_when_no_gas_estimate_key(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"other": "data"})
        )

        price = await sdk._fetch_gas_price_estimation()
        # DEFAULT_GAS_ESTIMATE = 100
        assert price == 100

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(500, text="Server Error")
        )

        with pytest.raises(ValueError, match="Failed to fetch gas price"):
            await sdk._fetch_gas_price_estimation()

    @pytest.mark.asyncio
    async def test_uses_node_api_key_in_headers(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptions(node_api_key="my-node-key")
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"gas_estimate": 200})
        )

        await sdk._fetch_gas_price_estimation()
        call_kwargs = sdk._http_client.get.call_args.kwargs
        assert call_kwargs["headers"]["x-api-key"] == "my-node-key"


# ---------------------------------------------------------------------------
# BaseSDK._simulate_transaction
# ---------------------------------------------------------------------------


class TestBaseSDKSimulateTransaction:
    @pytest.mark.asyncio
    async def test_success_returns_first_item(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sim_data = [{"max_gas_amount": "50000", "gas_unit_price": "100", "success": True}]
        sdk._http_client = AsyncMock()
        sdk._http_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data=sim_data)
        )

        mock_txn = MagicMock()
        mock_txn.fee_payer_address = None
        # Need _serialize_for_simulation to return bytes
        with patch.object(sdk, "_serialize_for_simulation", return_value=b"\x00" * 16):
            result = await sdk._simulate_transaction(mock_txn)

        assert result["max_gas_amount"] == "50000"
        assert result["gas_unit_price"] == "100"

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        sdk._http_client.post = AsyncMock(
            return_value=_make_httpx_response(400, text="Bad Request")
        )

        mock_txn = MagicMock()
        with patch.object(sdk, "_serialize_for_simulation", return_value=b"\x00" * 16):
            with pytest.raises(ValueError, match="Transaction simulation failed"):
                await sdk._simulate_transaction(mock_txn)

    @pytest.mark.asyncio
    async def test_empty_list_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._http_client = AsyncMock()
        sdk._http_client.post = AsyncMock(return_value=_make_httpx_response(200, json_data=[]))

        mock_txn = MagicMock()
        with patch.object(sdk, "_serialize_for_simulation", return_value=b"\x00" * 16):
            with pytest.raises(ValueError, match="empty results"):
                await sdk._simulate_transaction(mock_txn)


# ---------------------------------------------------------------------------
# BaseSDK._submit_direct
# ---------------------------------------------------------------------------


class TestBaseSDKSubmitDirect:
    @pytest.mark.asyncio
    async def test_success(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)

        mock_raw_txn = MagicMock()
        mock_raw_txn.sender = "0x" + "aa" * 32
        mock_raw_txn.sequence_number = 1
        mock_raw_txn.max_gas_amount = 200000
        mock_raw_txn.gas_unit_price = 100
        mock_raw_txn.expiration_timestamps_secs = 9999999999

        mock_txn = MagicMock()
        mock_txn.raw_transaction = mock_raw_txn
        mock_txn.fee_payer_address = None

        mock_auth = MagicMock()
        sdk._http_client = AsyncMock()
        sdk._http_client.post = AsyncMock(
            return_value=_make_httpx_response(200, json_data={"hash": "0xabc123"})
        )

        with patch.object(sdk, "_serialize_signed_transaction", return_value=b"\x00" * 16):
            result = await sdk._submit_direct(mock_txn, mock_auth)

        assert result.hash == "0xabc123"
        assert isinstance(result, PendingTransactionResponse)

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        mock_txn = MagicMock()
        mock_auth = MagicMock()
        sdk._http_client = AsyncMock()
        sdk._http_client.post = AsyncMock(
            return_value=_make_httpx_response(400, text="Bad Request")
        )

        with patch.object(sdk, "_serialize_signed_transaction", return_value=b"\x00" * 16):
            with pytest.raises(ValueError, match="Transaction submission failed"):
                await sdk._submit_direct(mock_txn, mock_auth)


# ---------------------------------------------------------------------------
# BaseSDK._wait_for_transaction
# ---------------------------------------------------------------------------


class TestBaseSDKWaitForTransaction:
    @pytest.mark.asyncio
    async def test_success_on_first_poll(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True, "hash": "0xabc"}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data=success_data)
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            result = await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=30.0)

        assert result["hash"] == "0xabc"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_pending_then_success(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        pending_data = {"type": "pending_transaction"}
        success_data = {"type": "user_transaction", "success": True, "hash": "0xabc"}

        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            side_effect=[
                _make_httpx_response(200, json_data=pending_data),
                _make_httpx_response(200, json_data=success_data),
            ]
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            result = await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=30.0)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_failure_vm_status_raises_txn_confirm_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)
        failed_data = {"type": "user_transaction", "success": False, "vm_status": "Out of gas"}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data=failed_data)
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            with pytest.raises(TxnConfirmError, match="failed: Out of gas"):
                await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=30.0)

    @pytest.mark.asyncio
    async def test_timeout_raises_txn_confirm_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)
        pending_data = {"type": "pending_transaction"}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data=pending_data)
        )

        # Very short timeout so it fires immediately
        with patch("time.time", side_effect=[0.0, 100.0]):
            with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
                with pytest.raises(TxnConfirmError, match="did not confirm"):
                    await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=0.001)

    @pytest.mark.asyncio
    async def test_connect_timeout_is_swallowed(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True, "hash": "0xabc"}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            side_effect=[
                httpx.ConnectTimeout("timeout"),
                _make_httpx_response(200, json_data=success_data),
            ]
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            result = await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=30.0)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_read_timeout_is_swallowed(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True, "hash": "0xabc"}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            side_effect=[
                httpx.ReadTimeout("read timeout"),
                _make_httpx_response(200, json_data=success_data),
            ]
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            result = await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=30.0)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_connect_error_is_swallowed(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True, "hash": "0xabc"}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                _make_httpx_response(200, json_data=success_data),
            ]
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            result = await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=30.0)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_uses_default_timeout_when_none(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True}
        sdk._http_client = AsyncMock()
        sdk._http_client.get = AsyncMock(
            return_value=_make_httpx_response(200, json_data=success_data)
        )

        with patch.object(sdk, "_async_sleep", new_callable=AsyncMock):
            result = await sdk._wait_for_transaction("0xabc", txn_confirm_timeout=None)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# BaseSDK.build_tx
# ---------------------------------------------------------------------------


class TestBaseSDKBuildTx:
    @pytest.mark.asyncio
    async def test_build_tx_with_gas_price_manager_cached(
        self, test_config: Any, mock_account: Any
    ) -> None:
        mock_manager = MagicMock()
        mock_manager.get_gas_price.return_value = 150
        opts = BaseSDKOptions(gas_price_manager=mock_manager)
        sdk = _make_sdk(test_config, mock_account, opts)

        mock_abi = MagicMock()
        mock_abi.params = ["&signer", "u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()

        mock_txn = MagicMock()
        with patch(
            "decibel._base.build_simple_transaction_sync", return_value=mock_txn
        ) as mock_build:
            with patch("decibel._base.generate_random_replay_protection_nonce", return_value=12345):
                result = await sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[42], type_arguments=[]),
                    sender,
                )

        assert result is mock_txn
        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["gas_unit_price"] == 150

    @pytest.mark.asyncio
    async def test_build_tx_with_gas_price_manager_uncached(
        self, test_config: Any, mock_account: Any
    ) -> None:
        # gas_price_manager.fetch_and_set_gas_price is awaited in build_tx,
        # so use a regular MagicMock whose get_gas_price returns None and
        # whose fetch_and_set_gas_price is an AsyncMock coroutine.
        mock_manager = MagicMock()
        mock_manager.get_gas_price.return_value = None
        mock_manager.fetch_and_set_gas_price = AsyncMock(return_value=200)
        opts = BaseSDKOptions(gas_price_manager=mock_manager)
        sdk = _make_sdk(test_config, mock_account, opts)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()

        mock_txn = MagicMock()
        with patch(
            "decibel._base.build_simple_transaction_sync", return_value=mock_txn
        ) as mock_build:
            with patch("decibel._base.generate_random_replay_protection_nonce", return_value=999):
                await sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[42], type_arguments=[]),
                    sender,
                )

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["gas_unit_price"] == 200

    @pytest.mark.asyncio
    async def test_build_tx_without_gas_manager_fetches_price(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()
        mock_txn = MagicMock()

        with patch.object(
            sdk, "_fetch_gas_price_estimation", new_callable=AsyncMock, return_value=123
        ):
            with patch(
                "decibel._base.build_simple_transaction_sync", return_value=mock_txn
            ) as mock_build:
                with patch(
                    "decibel._base.generate_random_replay_protection_nonce", return_value=111
                ):
                    await sdk.build_tx(
                        MagicMock(function="0x1::m::f", function_arguments=[1], type_arguments=[]),
                        sender,
                    )

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["gas_unit_price"] == 123

    @pytest.mark.asyncio
    async def test_build_tx_explicit_gas_unit_price(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()
        mock_txn = MagicMock()

        with patch(
            "decibel._base.build_simple_transaction_sync", return_value=mock_txn
        ) as mock_build:
            with patch("decibel._base.generate_random_replay_protection_nonce", return_value=222):
                await sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[1], type_arguments=[]),
                    sender,
                    gas_unit_price=500,
                )

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["gas_unit_price"] == 500

    @pytest.mark.asyncio
    async def test_build_tx_missing_abi_raises(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = None  # Missing ABI

        sender = MagicMock()

        with patch("decibel._base.generate_random_replay_protection_nonce", return_value=333):
            with pytest.raises(ValueError, match="Cannot build transaction"):
                await sdk.build_tx(
                    MagicMock(function="0x1::m::unknown", function_arguments=[], type_arguments=[]),
                    sender,
                )

    @pytest.mark.asyncio
    async def test_build_tx_nonce_none_raises(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)

        with patch("decibel._base.generate_random_replay_protection_nonce", return_value=None):
            with pytest.raises(ValueError, match="replay protection nonce"):
                await sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[], type_arguments=[]),
                    MagicMock(),
                )


# ---------------------------------------------------------------------------
# BaseSDK.submit_tx
# ---------------------------------------------------------------------------


class TestBaseSDKSubmitTx:
    @pytest.mark.asyncio
    async def test_no_fee_payer_calls_submit_direct(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(no_fee_payer=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        mock_txn = MagicMock()
        mock_auth = MagicMock()
        expected = _make_pending_response()

        with patch.object(sdk, "_submit_direct", new_callable=AsyncMock, return_value=expected):
            result = await sdk.submit_tx(mock_txn, mock_auth)

        assert result is expected

    @pytest.mark.asyncio
    async def test_with_fee_payer_calls_submit_fee_paid(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(no_fee_payer=False)
        sdk = _make_sdk(test_config, mock_account, opts)
        mock_txn = MagicMock()
        mock_auth = MagicMock()
        expected = _make_pending_response()

        with patch(
            "decibel._base.submit_fee_paid_transaction",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await sdk.submit_tx(mock_txn, mock_auth)

        assert result is expected


# ---------------------------------------------------------------------------
# BaseSDK._sign_transaction
# ---------------------------------------------------------------------------


class TestBaseSDKSignTransaction:
    def test_sign_without_fee_payer(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        signer = MagicMock()
        mock_raw_txn = MagicMock()
        mock_auth = MagicMock()
        mock_raw_txn.sign.return_value = mock_auth

        mock_txn = MagicMock()
        mock_txn.raw_transaction = mock_raw_txn
        mock_txn.fee_payer_address = None

        result = sdk._sign_transaction(signer, mock_txn)
        mock_raw_txn.sign.assert_called_once_with(signer.private_key)
        assert result is mock_auth

    def test_sign_with_fee_payer(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        signer = MagicMock()
        mock_raw_txn = MagicMock()
        mock_auth = MagicMock()

        mock_txn = MagicMock()
        mock_txn.raw_transaction = mock_raw_txn
        mock_txn.fee_payer_address = MagicMock()  # Not None

        with patch("decibel._base.FeePayerRawTransaction") as mock_fee_payer_cls:
            mock_fee_payer_instance = MagicMock()
            mock_fee_payer_instance.sign.return_value = mock_auth
            mock_fee_payer_cls.return_value = mock_fee_payer_instance

            result = sdk._sign_transaction(signer, mock_txn)

        mock_fee_payer_instance.sign.assert_called_once_with(signer.private_key)
        assert result is mock_auth


# ---------------------------------------------------------------------------
# BaseSDK._send_tx full flow
# ---------------------------------------------------------------------------


class TestBaseSDKSendTx:
    @pytest.mark.asyncio
    async def test_send_tx_skip_simulate(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)

        mock_txn = MagicMock()
        mock_auth = MagicMock()
        mock_pending = _make_pending_response("0xresult")
        success_data = {"type": "user_transaction", "success": True}

        mock_account.address.return_value = MagicMock()
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=mock_txn):
            with patch.object(sdk, "_sign_transaction", return_value=mock_auth):
                with patch.object(
                    sdk, "submit_tx", new_callable=AsyncMock, return_value=mock_pending
                ):
                    with patch.object(
                        sdk,
                        "_wait_for_transaction",
                        new_callable=AsyncMock,
                        return_value=success_data,
                    ):
                        result = await sdk._send_tx(MagicMock())

        assert result == success_data

    @pytest.mark.asyncio
    async def test_send_tx_with_simulate(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptions(skip_simulate=False)
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._account = mock_account

        mock_txn1 = MagicMock()
        mock_txn2 = MagicMock()
        mock_auth = MagicMock()
        mock_pending = _make_pending_response("0xresult2")
        success_data = {"type": "user_transaction", "success": True}
        sim_result = {"max_gas_amount": "100000", "gas_unit_price": "150"}

        build_tx_mock = AsyncMock(side_effect=[mock_txn1, mock_txn2])

        with patch.object(sdk, "build_tx", build_tx_mock):
            with patch.object(
                sdk, "_simulate_transaction", new_callable=AsyncMock, return_value=sim_result
            ):
                with patch.object(sdk, "_sign_transaction", return_value=mock_auth):
                    with patch.object(
                        sdk, "submit_tx", new_callable=AsyncMock, return_value=mock_pending
                    ):
                        with patch.object(
                            sdk,
                            "_wait_for_transaction",
                            new_callable=AsyncMock,
                            return_value=success_data,
                        ):
                            result = await sdk._send_tx(MagicMock())

        assert result == success_data
        assert build_tx_mock.await_count == 2  # built twice (initial + post-simulate)

    @pytest.mark.asyncio
    async def test_send_tx_simulate_missing_fields_raises(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(skip_simulate=False)
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._account = mock_account

        sim_result: dict[str, Any] = {}  # Missing max_gas_amount and gas_unit_price

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=MagicMock()):
            with patch.object(
                sdk, "_simulate_transaction", new_callable=AsyncMock, return_value=sim_result
            ):
                with pytest.raises(ValueError, match="Transaction simulation returned no results"):
                    await sdk._send_tx(MagicMock())

    @pytest.mark.asyncio
    async def test_send_tx_submit_connect_timeout_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(
                    sdk,
                    "submit_tx",
                    new_callable=AsyncMock,
                    side_effect=httpx.ConnectTimeout("timeout"),
                ):
                    with pytest.raises(TxnSubmitError, match="connection timeout"):
                        await sdk._send_tx(MagicMock())

    @pytest.mark.asyncio
    async def test_send_tx_submit_connect_error_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(
                    sdk,
                    "submit_tx",
                    new_callable=AsyncMock,
                    side_effect=httpx.ConnectError("refused"),
                ):
                    with pytest.raises(TxnSubmitError, match="connection error"):
                        await sdk._send_tx(MagicMock())

    @pytest.mark.asyncio
    async def test_send_tx_submit_generic_error_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(
                    sdk, "submit_tx", new_callable=AsyncMock, side_effect=RuntimeError("generic")
                ):
                    with pytest.raises(TxnSubmitError):
                        await sdk._send_tx(MagicMock())

    @pytest.mark.asyncio
    async def test_send_tx_with_account_override(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)

        override_account = MagicMock()
        override_account.address.return_value = MagicMock()
        mock_pending = _make_pending_response()
        success_data = {"success": True}

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(
                    sdk, "submit_tx", new_callable=AsyncMock, return_value=mock_pending
                ):
                    with patch.object(
                        sdk,
                        "_wait_for_transaction",
                        new_callable=AsyncMock,
                        return_value=success_data,
                    ):
                        result = await sdk._send_tx(MagicMock(), account_override=override_account)

        assert result == success_data


# ---------------------------------------------------------------------------
# BaseSDKSync.__init__
# ---------------------------------------------------------------------------


class TestBaseSDKSyncInit:
    @patch("decibel._base.AbiRegistry")
    def test_creates_default_http_client(self, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        sdk = BaseSDKSync(config=test_config, account=account)
        assert isinstance(sdk._http_client, httpx.Client)
        assert sdk._owns_http_client is True

    @patch("decibel._base.AbiRegistry")
    def test_uses_provided_http_client(self, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        provided_client = MagicMock(spec=httpx.Client)
        opts = BaseSDKOptionsSync(http_client=provided_client)
        sdk = BaseSDKSync(config=test_config, account=account, opts=opts)
        assert sdk._http_client is provided_client
        assert sdk._owns_http_client is False

    @patch("decibel._base.AbiRegistry")
    def test_default_opts(self, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        sdk = BaseSDKSync(config=test_config, account=account)
        assert sdk._skip_simulate is False
        assert sdk._no_fee_payer is False
        assert sdk._node_api_key is None
        assert sdk._gas_price_manager is None

    @patch("decibel._base.AbiRegistry")
    def test_none_chain_id_logs_warning(self, mock_abi: Any, test_config: Any) -> None:
        import logging
        from dataclasses import replace

        config_no_chain = replace(test_config, chain_id=None)
        account = MagicMock()
        with patch.object(logging.getLogger("decibel._base"), "warning") as mock_warn:
            BaseSDKSync(config=config_no_chain, account=account)
            mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# BaseSDKSync.close / context manager
# ---------------------------------------------------------------------------


class TestBaseSDKSyncClose:
    def test_close_closes_owned_client(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._owns_http_client = True

        sdk.close()
        sdk._http_client.close.assert_called_once()

    def test_close_does_not_close_provided_client(
        self, test_config: Any, mock_account: Any
    ) -> None:
        provided_client = MagicMock(spec=httpx.Client)
        opts = BaseSDKOptionsSync(http_client=provided_client)
        sdk = _make_sdk_sync(test_config, mock_account, opts)

        sdk.close()
        provided_client.close.assert_not_called()

    def test_enter_returns_self(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        result = sdk.__enter__()
        assert result is sdk

    def test_exit_calls_close(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk.close = MagicMock()  # type: ignore[method-assign]
        sdk.__exit__(None, None, None)
        sdk.close.assert_called_once()

    def test_context_manager(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        with sdk as ctx:
            assert ctx is sdk
        sdk._http_client.close.assert_called_once()


# ---------------------------------------------------------------------------
# BaseSDKSync._fetch_gas_price_estimation
# ---------------------------------------------------------------------------


class TestBaseSDKSyncFetchGasPrice:
    def test_success(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            return_value=_make_httpx_response(200, json_data={"gas_estimate": 250})
        )

        price = sdk._fetch_gas_price_estimation()
        assert price == 250

    def test_uses_default_when_missing(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(return_value=_make_httpx_response(200, json_data={}))

        price = sdk._fetch_gas_price_estimation()
        assert price == 100  # DEFAULT_GAS_ESTIMATE

    def test_failure_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            return_value=_make_httpx_response(503, text="Service Unavailable")
        )

        with pytest.raises(ValueError, match="Failed to fetch gas price"):
            sdk._fetch_gas_price_estimation()


# ---------------------------------------------------------------------------
# BaseSDKSync._simulate_transaction
# ---------------------------------------------------------------------------


class TestBaseSDKSyncSimulateTransaction:
    def test_success_returns_first_item(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sim_data = [{"max_gas_amount": "75000", "gas_unit_price": "100"}]
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data=sim_data)
        )

        mock_txn = MagicMock()
        with patch.object(sdk, "_serialize_for_simulation", return_value=b"\x00" * 8):
            result = sdk._simulate_transaction(mock_txn)

        assert result["max_gas_amount"] == "75000"

    def test_failure_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.post = MagicMock(return_value=_make_httpx_response(400, text="Bad"))

        mock_txn = MagicMock()
        with patch.object(sdk, "_serialize_for_simulation", return_value=b"\x00" * 8):
            with pytest.raises(ValueError, match="simulation failed"):
                sdk._simulate_transaction(mock_txn)

    def test_empty_list_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.post = MagicMock(return_value=_make_httpx_response(200, json_data=[]))

        mock_txn = MagicMock()
        with patch.object(sdk, "_serialize_for_simulation", return_value=b"\x00" * 8):
            with pytest.raises(ValueError, match="empty results"):
                sdk._simulate_transaction(mock_txn)


# ---------------------------------------------------------------------------
# BaseSDKSync._submit_direct
# ---------------------------------------------------------------------------


class TestBaseSDKSyncSubmitDirect:
    def test_success(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)

        mock_raw = MagicMock()
        mock_raw.sender = "0x" + "aa" * 32
        mock_raw.sequence_number = 1
        mock_raw.max_gas_amount = 200000
        mock_raw.gas_unit_price = 100
        mock_raw.expiration_timestamps_secs = 9999999999

        mock_txn = MagicMock()
        mock_txn.raw_transaction = mock_raw
        mock_auth = MagicMock()

        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.post = MagicMock(
            return_value=_make_httpx_response(200, json_data={"hash": "0xsync123"})
        )

        with patch.object(sdk, "_serialize_signed_transaction", return_value=b"\x00" * 8):
            result = sdk._submit_direct(mock_txn, mock_auth)

        assert result.hash == "0xsync123"

    def test_failure_raises_value_error(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.post = MagicMock(
            return_value=_make_httpx_response(400, text="Bad Request")
        )

        mock_txn = MagicMock()
        mock_auth = MagicMock()

        with patch.object(sdk, "_serialize_signed_transaction", return_value=b"\x00" * 8):
            with pytest.raises(ValueError, match="submission failed"):
                sdk._submit_direct(mock_txn, mock_auth)


# ---------------------------------------------------------------------------
# BaseSDKSync._wait_for_transaction
# ---------------------------------------------------------------------------


class TestBaseSDKSyncWaitForTransaction:
    def test_success_on_first_poll(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True, "hash": "0xsync"}
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            return_value=_make_httpx_response(200, json_data=success_data)
        )

        with patch("time.sleep"):
            result = sdk._wait_for_transaction("0xsync", txn_confirm_timeout=30.0)

        assert result["success"] is True

    def test_pending_then_success(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        pending_data = {"type": "pending_transaction"}
        success_data = {"type": "user_transaction", "success": True}

        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            side_effect=[
                _make_httpx_response(200, json_data=pending_data),
                _make_httpx_response(200, json_data=success_data),
            ]
        )

        with patch("time.sleep"):
            result = sdk._wait_for_transaction("0xsync", txn_confirm_timeout=30.0)

        assert result["success"] is True

    def test_failure_vm_status_raises(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        failed_data = {"type": "user_transaction", "success": False, "vm_status": "Aborted"}
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            return_value=_make_httpx_response(200, json_data=failed_data)
        )

        with patch("time.sleep"), pytest.raises(TxnConfirmError, match="failed: Aborted"):
            sdk._wait_for_transaction("0xsync", txn_confirm_timeout=30.0)

    def test_timeout_raises(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        pending_data = {"type": "pending_transaction"}
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            return_value=_make_httpx_response(200, json_data=pending_data)
        )

        with patch("time.time", side_effect=[0.0, 100.0]), patch("time.sleep"):
            with pytest.raises(TxnConfirmError, match="did not confirm"):
                sdk._wait_for_transaction("0xsync", txn_confirm_timeout=0.001)

    def test_uses_default_timeout_when_none(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        success_data = {"type": "user_transaction", "success": True}
        sdk._http_client = MagicMock(spec=httpx.Client)
        sdk._http_client.get = MagicMock(
            return_value=_make_httpx_response(200, json_data=success_data)
        )

        with patch("time.sleep"):
            result = sdk._wait_for_transaction("0xsync", txn_confirm_timeout=None)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# BaseSDKSync._send_tx
# ---------------------------------------------------------------------------


class TestBaseSDKSyncSendTx:
    def test_send_tx_skip_simulate(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        mock_txn = MagicMock()
        mock_auth = MagicMock()
        mock_pending = _make_pending_response()
        success_data = {"success": True}

        with patch.object(sdk, "build_tx", return_value=mock_txn):
            with patch.object(sdk, "_sign_transaction", return_value=mock_auth):
                with patch.object(sdk, "submit_tx", return_value=mock_pending):
                    with patch.object(sdk, "_wait_for_transaction", return_value=success_data):
                        result = sdk._send_tx(MagicMock())

        assert result == success_data

    def test_send_tx_connect_timeout_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(sdk, "submit_tx", side_effect=httpx.ConnectTimeout("timeout")):
                    with pytest.raises(TxnSubmitError, match="connection timeout"):
                        sdk._send_tx(MagicMock())

    def test_send_tx_generic_error_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(sdk, "submit_tx", side_effect=RuntimeError("boom")):
                    with pytest.raises(TxnSubmitError):
                        sdk._send_tx(MagicMock())


# ---------------------------------------------------------------------------
# BaseSDKSync.submit_tx
# ---------------------------------------------------------------------------


class TestBaseSDKSyncSubmitTx:
    def test_no_fee_payer_calls_submit_direct(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(no_fee_payer=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        expected = _make_pending_response()

        with patch.object(sdk, "_submit_direct", return_value=expected):
            result = sdk.submit_tx(MagicMock(), MagicMock())

        assert result is expected

    def test_with_fee_payer_calls_submit_fee_paid_sync(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptionsSync(no_fee_payer=False)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        expected = _make_pending_response()

        with patch("decibel._base.submit_fee_paid_transaction_sync", return_value=expected):
            result = sdk.submit_tx(MagicMock(), MagicMock())

        assert result is expected


# ---------------------------------------------------------------------------
# get_primary_subaccount_address (method)
# ---------------------------------------------------------------------------


class TestGetPrimarySubaccountAddress:
    def test_delegates_to_util(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        test_addr = "0x" + "aa" * 32
        with patch(
            "decibel._base.get_primary_subaccount_addr", return_value="0xderived"
        ) as mock_fn:
            result = sdk.get_primary_subaccount_address(test_addr)

        assert result == "0xderived"
        mock_fn.assert_called_once_with(
            test_addr, test_config.compat_version, test_config.deployment.package
        )


# ---------------------------------------------------------------------------
# BaseSDK — additional properties and serialization coverage
# ---------------------------------------------------------------------------


class TestBaseSDKProperties:
    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_aptos_property(self, mock_rest: Any, mock_abi: Any, test_config: Any) -> None:
        account = MagicMock()
        mock_rest_instance = MagicMock()
        mock_rest.return_value = mock_rest_instance
        sdk = BaseSDK(config=test_config, account=account)
        assert sdk.aptos is mock_rest_instance

    def test_skip_simulate_property(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        assert sdk.skip_simulate is True

    def test_no_fee_payer_property(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptions(no_fee_payer=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        assert sdk.no_fee_payer is True

    def test_config_property(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        assert sdk.config is test_config

    def test_account_property(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk(test_config, mock_account)
        assert sdk.account is mock_account


class TestBaseSDKSyncProperties:
    def test_config_property(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        assert sdk.config is test_config

    def test_account_property(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        assert sdk.account is mock_account

    def test_skip_simulate_property(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        assert sdk.skip_simulate is True

    def test_no_fee_payer_property(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(no_fee_payer=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        assert sdk.no_fee_payer is True

    def test_time_delta_ms_property(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(time_delta_ms=250)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        assert sdk.time_delta_ms == 250

    def test_time_delta_ms_setter(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk.time_delta_ms = 1500
        assert sdk.time_delta_ms == 1500

    def test_get_primary_subaccount_address_delegates(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        test_addr = "0x" + "aa" * 32
        with patch("decibel._base.get_primary_subaccount_addr", return_value="0xsync_derived"):
            result = sdk.get_primary_subaccount_address(test_addr)
        assert result == "0xsync_derived"


# ---------------------------------------------------------------------------
# BaseSDKSync.build_tx — gas manager paths
# ---------------------------------------------------------------------------


class TestBaseSDKSyncBuildTx:
    def test_build_tx_with_gas_price_manager_cached(
        self, test_config: Any, mock_account: Any
    ) -> None:
        mock_manager = MagicMock()
        mock_manager.get_gas_price.return_value = 300
        opts = BaseSDKOptionsSync(gas_price_manager=mock_manager)
        sdk = _make_sdk_sync(test_config, mock_account, opts)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()
        mock_txn = MagicMock()
        with patch(
            "decibel._base.build_simple_transaction_sync", return_value=mock_txn
        ) as mock_build:
            with patch("decibel._base.generate_random_replay_protection_nonce", return_value=111):
                result = sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[1], type_arguments=[]),
                    sender,
                )

        assert result is mock_txn
        assert mock_build.call_args.kwargs["gas_unit_price"] == 300

    def test_build_tx_with_gas_price_manager_uncached(
        self, test_config: Any, mock_account: Any
    ) -> None:
        mock_manager = MagicMock()
        mock_manager.get_gas_price.return_value = None
        mock_manager.fetch_and_set_gas_price.return_value = 400
        opts = BaseSDKOptionsSync(gas_price_manager=mock_manager)
        sdk = _make_sdk_sync(test_config, mock_account, opts)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()
        mock_txn = MagicMock()
        with patch(
            "decibel._base.build_simple_transaction_sync", return_value=mock_txn
        ) as mock_build:
            with patch("decibel._base.generate_random_replay_protection_nonce", return_value=222):
                sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[1], type_arguments=[]),
                    sender,
                )

        assert mock_build.call_args.kwargs["gas_unit_price"] == 400

    def test_build_tx_missing_abi_raises(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = None

        with patch("decibel._base.generate_random_replay_protection_nonce", return_value=333):
            with pytest.raises(ValueError, match="Cannot build transaction"):
                sdk.build_tx(
                    MagicMock(function="0x1::m::unknown", function_arguments=[], type_arguments=[]),
                    MagicMock(),
                )

    def test_build_tx_nonce_none_raises(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        with patch("decibel._base.generate_random_replay_protection_nonce", return_value=None):
            with pytest.raises(ValueError, match="replay protection nonce"):
                sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[], type_arguments=[]),
                    MagicMock(),
                )

    def test_build_tx_without_gas_manager_fetches_price(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        sender = MagicMock()
        mock_txn = MagicMock()

        with patch.object(sdk, "_fetch_gas_price_estimation", return_value=500):
            with patch(
                "decibel._base.build_simple_transaction_sync", return_value=mock_txn
            ) as mock_build:
                with patch(
                    "decibel._base.generate_random_replay_protection_nonce", return_value=444
                ):
                    sdk.build_tx(
                        MagicMock(function="0x1::m::f", function_arguments=[1], type_arguments=[]),
                        sender,
                    )

        assert mock_build.call_args.kwargs["gas_unit_price"] == 500

    def test_build_tx_explicit_gas_unit_price(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)

        mock_abi = MagicMock()
        mock_abi.params = ["u64"]
        sdk._abi_registry = MagicMock()
        sdk._abi_registry.get_function.return_value = mock_abi

        mock_txn = MagicMock()
        with patch(
            "decibel._base.build_simple_transaction_sync", return_value=mock_txn
        ) as mock_build:
            with patch("decibel._base.generate_random_replay_protection_nonce", return_value=555):
                sdk.build_tx(
                    MagicMock(function="0x1::m::f", function_arguments=[1], type_arguments=[]),
                    MagicMock(),
                    gas_unit_price=600,
                )

        assert mock_build.call_args.kwargs["gas_unit_price"] == 600


# ---------------------------------------------------------------------------
# BaseSDKSync._send_tx — with simulate path
# ---------------------------------------------------------------------------


class TestBaseSDKSyncSendTxWithSimulate:
    def test_send_tx_with_simulate(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=False)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        mock_txn1 = MagicMock()
        mock_txn2 = MagicMock()
        mock_auth = MagicMock()
        mock_pending = _make_pending_response()
        success_data = {"success": True}
        sim_result = {"max_gas_amount": "100000", "gas_unit_price": "150"}

        build_tx_mock = MagicMock(side_effect=[mock_txn1, mock_txn2])

        with patch.object(sdk, "build_tx", build_tx_mock):
            with patch.object(sdk, "_simulate_transaction", return_value=sim_result):
                with patch.object(sdk, "_sign_transaction", return_value=mock_auth):
                    with patch.object(sdk, "submit_tx", return_value=mock_pending):
                        with patch.object(sdk, "_wait_for_transaction", return_value=success_data):
                            result = sdk._send_tx(MagicMock())

        assert result == success_data
        assert build_tx_mock.call_count == 2

    def test_send_tx_simulate_missing_fields_raises(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=False)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", return_value=MagicMock()):
            with patch.object(sdk, "_simulate_transaction", return_value={}):
                with pytest.raises(ValueError, match="no results"):
                    sdk._send_tx(MagicMock())

    def test_send_tx_connect_error_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        with patch.object(sdk, "build_tx", return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(sdk, "submit_tx", side_effect=httpx.ConnectError("refused")):
                    with pytest.raises(TxnSubmitError, match="connection error"):
                        sdk._send_tx(MagicMock())

    def test_send_tx_http_status_error_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptionsSync(skip_simulate=True)
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        sdk._account = mock_account

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch.object(sdk, "build_tx", return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(
                    sdk,
                    "submit_tx",
                    side_effect=httpx.HTTPStatusError(
                        "rate limited", request=MagicMock(), response=mock_response
                    ),
                ):
                    with pytest.raises(TxnSubmitError, match="HTTP 429"):
                        sdk._send_tx(MagicMock())


# ---------------------------------------------------------------------------
# BaseSDK._send_tx — HTTP status error path
# ---------------------------------------------------------------------------


class TestBaseSDKAsyncSleep:
    @pytest.mark.asyncio
    async def test_async_sleep_calls_asyncio_sleep(
        self, test_config: Any, mock_account: Any
    ) -> None:
        sdk = _make_sdk(test_config, mock_account)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await sdk._async_sleep(0.1)
        mock_sleep.assert_awaited_once_with(0.1)


class TestBaseSDKSyncSignTransaction:
    def test_sign_without_fee_payer(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        signer = MagicMock()
        mock_raw_txn = MagicMock()
        mock_auth = MagicMock()
        mock_raw_txn.sign.return_value = mock_auth

        mock_txn = MagicMock()
        mock_txn.raw_transaction = mock_raw_txn
        mock_txn.fee_payer_address = None

        result = sdk._sign_transaction(signer, mock_txn)
        mock_raw_txn.sign.assert_called_once_with(signer.private_key)
        assert result is mock_auth

    def test_sign_with_fee_payer(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        signer = MagicMock()
        mock_raw_txn = MagicMock()
        mock_auth = MagicMock()

        mock_txn = MagicMock()
        mock_txn.raw_transaction = mock_raw_txn
        mock_txn.fee_payer_address = MagicMock()  # Not None

        with patch("decibel._base.FeePayerRawTransaction") as mock_fee_payer_cls:
            mock_fee_payer_instance = MagicMock()
            mock_fee_payer_instance.sign.return_value = mock_auth
            mock_fee_payer_cls.return_value = mock_fee_payer_instance

            result = sdk._sign_transaction(signer, mock_txn)

        mock_fee_payer_instance.sign.assert_called_once_with(signer.private_key)
        assert result is mock_auth


class TestBaseSDKSyncBuildNodeHeaders:
    def test_no_api_key_returns_empty_dict(self, test_config: Any, mock_account: Any) -> None:
        sdk = _make_sdk_sync(test_config, mock_account)
        sdk._node_api_key = None
        headers = sdk._build_node_headers()
        assert headers == {}

    def test_with_api_key_includes_header(self, test_config: Any, mock_account: Any) -> None:
        opts = BaseSDKOptionsSync(node_api_key="sync-node-key")
        sdk = _make_sdk_sync(test_config, mock_account, opts)
        headers = sdk._build_node_headers()
        assert headers["x-api-key"] == "sync-node-key"


class TestBaseSDKSendTxHttpStatusError:
    @pytest.mark.asyncio
    async def test_send_tx_http_status_error_raises_txn_submit_error(
        self, test_config: Any, mock_account: Any
    ) -> None:
        opts = BaseSDKOptions(skip_simulate=True)
        sdk = _make_sdk(test_config, mock_account, opts)
        sdk._account = mock_account

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch.object(sdk, "build_tx", new_callable=AsyncMock, return_value=MagicMock()):
            with patch.object(sdk, "_sign_transaction", return_value=MagicMock()):
                with patch.object(
                    sdk,
                    "submit_tx",
                    new_callable=AsyncMock,
                    side_effect=httpx.HTTPStatusError(
                        "rate limited", request=MagicMock(), response=mock_response
                    ),
                ):
                    with pytest.raises(TxnSubmitError, match="HTTP 429"):
                        await sdk._send_tx(MagicMock())


# ---------------------------------------------------------------------------
# Serialization methods using real cryptographic keys
# ---------------------------------------------------------------------------


def _build_real_transaction(with_fee_payer: bool = True) -> Any:
    """Build a real SimpleTransaction using actual Aptos types."""
    from aptos_sdk.account import Account

    from decibel._transaction_builder import InputEntryFunctionData, build_simple_transaction_sync
    from decibel.abi import AbiRegistry

    acct = Account.generate()
    registry = AbiRegistry(chain_id=2)
    func_id = "0xe7da2794b1d8af76532ed95f38bfdf1136abfd8ea3a240189971988a83101b7f::usdc::mint"
    abi = registry.get_function(func_id)
    assert abi is not None

    data = InputEntryFunctionData(
        function=func_id,
        function_arguments=[str(acct.address()), 1_000_000],
        type_arguments=[],
    )
    return acct, build_simple_transaction_sync(
        sender=acct.address(),
        data=data,
        chain_id=2,
        gas_unit_price=100,
        abi=abi,
        with_fee_payer=with_fee_payer,
        replay_protection_nonce=99999,
    )


class TestBaseSDKSerializationMethods:
    """Tests for _serialize_for_simulation and _serialize_signed_transaction using real keys."""

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_serialize_for_simulation_with_fee_payer(
        self, mock_rest: Any, mock_abi: Any, test_config: Any
    ) -> None:
        from aptos_sdk.account import Account

        real_account = Account.generate()
        sdk = BaseSDK(config=test_config, account=real_account)
        _, txn = _build_real_transaction(with_fee_payer=True)

        result = sdk._serialize_for_simulation(txn)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_serialize_for_simulation_without_fee_payer(
        self, mock_rest: Any, mock_abi: Any, test_config: Any
    ) -> None:
        from aptos_sdk.account import Account

        real_account = Account.generate()
        sdk = BaseSDK(config=test_config, account=real_account)
        _, txn = _build_real_transaction(with_fee_payer=False)

        result = sdk._serialize_for_simulation(txn)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("decibel._base.AbiRegistry")
    @patch("decibel._base.RestClient")
    def test_serialize_signed_transaction(
        self, mock_rest: Any, mock_abi: Any, test_config: Any
    ) -> None:
        from aptos_sdk.account import Account

        real_account = Account.generate()
        sdk = BaseSDK(config=test_config, account=real_account)
        _, txn = _build_real_transaction(with_fee_payer=True)

        # Sign the transaction properly
        sender_auth = sdk._sign_transaction(real_account, txn)
        result = sdk._serialize_signed_transaction(txn, sender_auth)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestBaseSDKSyncSerializationMethods:
    """Tests for BaseSDKSync serialization methods using real keys."""

    @patch("decibel._base.AbiRegistry")
    def test_serialize_for_simulation_with_fee_payer(self, mock_abi: Any, test_config: Any) -> None:
        from aptos_sdk.account import Account

        real_account = Account.generate()
        sdk = BaseSDKSync(config=test_config, account=real_account)
        _, txn = _build_real_transaction(with_fee_payer=True)

        result = sdk._serialize_for_simulation(txn)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("decibel._base.AbiRegistry")
    def test_serialize_for_simulation_without_fee_payer(
        self, mock_abi: Any, test_config: Any
    ) -> None:
        from aptos_sdk.account import Account

        real_account = Account.generate()
        sdk = BaseSDKSync(config=test_config, account=real_account)
        _, txn = _build_real_transaction(with_fee_payer=False)

        result = sdk._serialize_for_simulation(txn)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @patch("decibel._base.AbiRegistry")
    def test_serialize_signed_transaction(self, mock_abi: Any, test_config: Any) -> None:
        from aptos_sdk.account import Account

        real_account = Account.generate()
        sdk = BaseSDKSync(config=test_config, account=real_account)
        _, txn = _build_real_transaction(with_fee_payer=True)

        sender_auth = sdk._sign_transaction(real_account, txn)
        result = sdk._serialize_signed_transaction(txn, sender_auth)
        assert isinstance(result, bytes)
        assert len(result) > 0
