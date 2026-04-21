from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from aptos_sdk.account import Account
from aptos_sdk.account_address import AccountAddress

import decibel._base as base_module
import decibel._fee_pay as fee_pay_module
from decibel._base import BaseSDK, BaseSDKOptions, BaseSDKOptionsSync, BaseSDKSync
from decibel._constants import TESTNET_CONFIG
from decibel._fee_pay import (
    PendingTransactionResponse,
    submit_fee_paid_transaction,
    submit_fee_paid_transaction_sync,
)
from decibel._transaction_builder import InputEntryFunctionData


class FakeResponse:
    def __init__(
        self,
        *,
        is_success: bool = True,
        payload: dict[str, Any] | None = None,
        status_code: int = 200,
        text: str = "ok",
    ) -> None:
        self.is_success = is_success
        self._payload = payload or {}
        self.status_code = status_code
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


class RecordingAsyncClient:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def post(
        self,
        url: str,
        *,
        content: bytes,
        headers: dict[str, str],
        timeout: float | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self._response


class RecordingSyncClient:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        content: bytes,
        headers: dict[str, str],
        timeout: float | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self._response


def _pending_response(hash_value: str = "0x1") -> PendingTransactionResponse:
    return PendingTransactionResponse(
        hash=hash_value,
        sender="0x1",
        sequence_number="1",
        max_gas_amount="1",
        gas_unit_price="1",
        expiration_timestamp_secs="1",
    )


def test_base_sdk_rejects_conflicting_fee_payer_options() -> None:
    with pytest.raises(ValueError, match="cannot be used together"):
        BaseSDK(
            TESTNET_CONFIG,
            Account.generate(),
            BaseSDKOptions(
                no_fee_payer=True,
                fee_payer_account=Account.generate(),
            ),
        )


def test_base_sdk_sync_rejects_conflicting_fee_payer_options() -> None:
    with pytest.raises(ValueError, match="cannot be used together"):
        BaseSDKSync(
            TESTNET_CONFIG,
            Account.generate(),
            BaseSDKOptionsSync(
                no_fee_payer=True,
                fee_payer_account=Account.generate(),
            ),
        )


@pytest.mark.asyncio
async def test_submit_tx_uses_direct_path_when_no_fee_payer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk = BaseSDK(
        TESTNET_CONFIG,
        Account.generate(),
        BaseSDKOptions(no_fee_payer=True),
    )
    tx = SimpleNamespace()
    sender_authenticator = SimpleNamespace()
    called = {"direct": False}

    async def fake_submit_direct(
        transaction: Any,
        authenticator: Any,
        txn_submit_timeout: float | None = None,
    ) -> PendingTransactionResponse:
        called["direct"] = True
        assert transaction is tx
        assert authenticator is sender_authenticator
        assert txn_submit_timeout == 2.5
        return _pending_response("0xdirect")

    async def fake_fee_paid(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        raise AssertionError("fee-paid path should not be used when no_fee_payer=True")

    monkeypatch.setattr(sdk, "_submit_direct", fake_submit_direct)
    monkeypatch.setattr(base_module, "submit_fee_paid_transaction", fake_fee_paid)

    response = await sdk.submit_tx(tx, sender_authenticator, txn_submit_timeout=2.5)
    assert response.hash == "0xdirect"
    assert called["direct"] is True


@pytest.mark.asyncio
async def test_submit_tx_passes_fee_payer_account_to_fee_paid_submitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fee_payer_account = Account.generate()
    sdk = BaseSDK(
        TESTNET_CONFIG,
        Account.generate(),
        BaseSDKOptions(fee_payer_account=fee_payer_account),
    )
    captured: dict[str, Any] = {}

    async def fake_fee_paid(
        config: Any,
        transaction: Any,
        sender_authenticator: Any,
        *,
        fee_payer_account: Account | None = None,
        txn_submit_timeout: float | None = None,
    ) -> PendingTransactionResponse:
        captured["config"] = config
        captured["transaction"] = transaction
        captured["sender_authenticator"] = sender_authenticator
        captured["fee_payer_account"] = fee_payer_account
        captured["txn_submit_timeout"] = txn_submit_timeout
        return _pending_response("0xfee")

    monkeypatch.setattr(base_module, "submit_fee_paid_transaction", fake_fee_paid)

    tx = SimpleNamespace()
    sender_authenticator = SimpleNamespace()
    response = await sdk.submit_tx(tx, sender_authenticator, txn_submit_timeout=3.0)

    assert response.hash == "0xfee"
    assert captured["config"] == TESTNET_CONFIG
    assert captured["transaction"] is tx
    assert captured["sender_authenticator"] is sender_authenticator
    assert captured["fee_payer_account"] is fee_payer_account
    assert captured["txn_submit_timeout"] == 3.0


def test_submit_tx_sync_passes_fee_payer_account_to_fee_paid_submitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fee_payer_account = Account.generate()
    sdk = BaseSDKSync(
        TESTNET_CONFIG,
        Account.generate(),
        BaseSDKOptionsSync(fee_payer_account=fee_payer_account),
    )
    captured: dict[str, Any] = {}

    def fake_fee_paid(
        config: Any,
        transaction: Any,
        sender_authenticator: Any,
        *,
        fee_payer_account: Account | None = None,
        txn_submit_timeout: float | None = None,
    ) -> PendingTransactionResponse:
        captured["config"] = config
        captured["transaction"] = transaction
        captured["sender_authenticator"] = sender_authenticator
        captured["fee_payer_account"] = fee_payer_account
        captured["txn_submit_timeout"] = txn_submit_timeout
        return _pending_response("0xsync-fee")

    monkeypatch.setattr(base_module, "submit_fee_paid_transaction_sync", fake_fee_paid)

    tx = SimpleNamespace()
    sender_authenticator = SimpleNamespace()
    response = sdk.submit_tx(tx, sender_authenticator, txn_submit_timeout=4.0)

    assert response.hash == "0xsync-fee"
    assert captured["config"] == TESTNET_CONFIG
    assert captured["transaction"] is tx
    assert captured["sender_authenticator"] is sender_authenticator
    assert captured["fee_payer_account"] is fee_payer_account
    assert captured["txn_submit_timeout"] == 4.0


@pytest.mark.asyncio
async def test_send_tx_overrides_fee_payer_address_in_local_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = Account.generate()
    fee_payer = Account.generate()
    sdk = BaseSDK(
        TESTNET_CONFIG,
        sender,
        BaseSDKOptions(
            skip_simulate=False,
            fee_payer_account=fee_payer,
        ),
    )
    built_transactions: list[SimpleNamespace] = []

    async def fake_build_tx(
        data: Any,
        sender_addr: Any,
        *,
        max_gas_amount: int | None = None,
        gas_unit_price: int | None = None,
    ) -> SimpleNamespace:
        _ = (data, sender_addr, max_gas_amount, gas_unit_price)
        tx = SimpleNamespace(fee_payer_address=AccountAddress.from_str("0x0"))
        built_transactions.append(tx)
        return tx

    async def fake_simulate(transaction: Any) -> dict[str, str]:
        _ = transaction
        return {"max_gas_amount": "100", "gas_unit_price": "2"}

    def fake_sign(signer: Any, transaction: Any) -> object:
        _ = (signer, transaction)
        return object()

    async def fake_submit(
        transaction: Any,
        sender_authenticator: Any,
        *,
        txn_submit_timeout: float | None = None,
    ) -> PendingTransactionResponse:
        _ = sender_authenticator
        assert txn_submit_timeout == 1.25
        assert transaction.fee_payer_address == fee_payer.address()
        return _pending_response("0xsend")

    async def fake_wait(
        tx_hash: str,
        txn_confirm_timeout: float | None = None,
        poll_interval_secs: float = 1.0,
    ) -> dict[str, Any]:
        _ = (txn_confirm_timeout, poll_interval_secs)
        return {"hash": tx_hash, "success": True}

    monkeypatch.setattr(sdk, "build_tx", fake_build_tx)
    monkeypatch.setattr(sdk, "_simulate_transaction", fake_simulate)
    monkeypatch.setattr(sdk, "_sign_transaction", fake_sign)
    monkeypatch.setattr(sdk, "submit_tx", fake_submit)
    monkeypatch.setattr(sdk, "_wait_for_transaction", fake_wait)

    result = await sdk._send_tx(
        InputEntryFunctionData(function="0x1::module::function"),
        txn_submit_timeout=1.25,
    )
    assert result["hash"] == "0xsend"
    assert len(built_transactions) == 2
    assert all(tx.fee_payer_address == fee_payer.address() for tx in built_transactions)


def test_send_tx_sync_overrides_fee_payer_address_in_local_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = Account.generate()
    fee_payer = Account.generate()
    sdk = BaseSDKSync(
        TESTNET_CONFIG,
        sender,
        BaseSDKOptionsSync(
            skip_simulate=False,
            fee_payer_account=fee_payer,
        ),
    )
    built_transactions: list[SimpleNamespace] = []

    def fake_build_tx(
        data: Any,
        sender_addr: Any,
        *,
        max_gas_amount: int | None = None,
        gas_unit_price: int | None = None,
    ) -> SimpleNamespace:
        _ = (data, sender_addr, max_gas_amount, gas_unit_price)
        tx = SimpleNamespace(fee_payer_address=AccountAddress.from_str("0x0"))
        built_transactions.append(tx)
        return tx

    def fake_simulate(transaction: Any) -> dict[str, str]:
        _ = transaction
        return {"max_gas_amount": "100", "gas_unit_price": "2"}

    def fake_sign(signer: Any, transaction: Any) -> object:
        _ = (signer, transaction)
        return object()

    def fake_submit(
        transaction: Any,
        sender_authenticator: Any,
        *,
        txn_submit_timeout: float | None = None,
    ) -> PendingTransactionResponse:
        _ = sender_authenticator
        assert txn_submit_timeout == 2.25
        assert transaction.fee_payer_address == fee_payer.address()
        return _pending_response("0xsend-sync")

    def fake_wait(
        tx_hash: str,
        txn_confirm_timeout: float | None = None,
        poll_interval_secs: float = 1.0,
    ) -> dict[str, Any]:
        _ = (txn_confirm_timeout, poll_interval_secs)
        return {"hash": tx_hash, "success": True}

    monkeypatch.setattr(sdk, "build_tx", fake_build_tx)
    monkeypatch.setattr(sdk, "_simulate_transaction", fake_simulate)
    monkeypatch.setattr(sdk, "_sign_transaction", fake_sign)
    monkeypatch.setattr(sdk, "submit_tx", fake_submit)
    monkeypatch.setattr(sdk, "_wait_for_transaction", fake_wait)

    result = sdk._send_tx(
        InputEntryFunctionData(function="0x1::module::function"),
        txn_submit_timeout=2.25,
    )
    assert result["hash"] == "0xsend-sync"
    assert len(built_transactions) == 2
    assert all(tx.fee_payer_address == fee_payer.address() for tx in built_transactions)


@pytest.mark.asyncio
async def test_fee_pay_async_prefers_local_mode_when_account_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"local": False}

    async def fake_local(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        called["local"] = True
        return _pending_response("0xlocal")

    async def fake_gas_station(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        raise AssertionError("gas station path should not be called when fee_payer_account is set")

    monkeypatch.setattr(fee_pay_module, "_submit_via_local_fee_payer", fake_local)
    monkeypatch.setattr(fee_pay_module, "_submit_via_gas_station_api", fake_gas_station)
    monkeypatch.setattr(fee_pay_module, "_submit_via_legacy_fee_payer", fake_gas_station)

    config = replace(TESTNET_CONFIG, gas_station_api_key="api-key")
    response = await submit_fee_paid_transaction(
        config,
        SimpleNamespace(),
        SimpleNamespace(),
        fee_payer_account=object(),
    )
    assert response.hash == "0xlocal"
    assert called["local"] is True


@pytest.mark.asyncio
async def test_fee_pay_async_routes_to_gas_station_api(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"api": False}

    async def fake_api(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        called["api"] = True
        return _pending_response("0xapi")

    monkeypatch.setattr(fee_pay_module, "_submit_via_gas_station_api", fake_api)
    config = replace(TESTNET_CONFIG, gas_station_api_key="api-key")
    response = await submit_fee_paid_transaction(config, SimpleNamespace(), SimpleNamespace())
    assert response.hash == "0xapi"
    assert called["api"] is True


@pytest.mark.asyncio
async def test_fee_pay_async_routes_to_legacy_url(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"legacy": False}

    async def fake_legacy(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        called["legacy"] = True
        return _pending_response("0xlegacy")

    monkeypatch.setattr(fee_pay_module, "_submit_via_legacy_fee_payer", fake_legacy)
    config = replace(TESTNET_CONFIG, gas_station_api_key=None, gas_station_url="https://fee-payer")
    response = await submit_fee_paid_transaction(config, SimpleNamespace(), SimpleNamespace())
    assert response.hash == "0xlegacy"
    assert called["legacy"] is True


@pytest.mark.asyncio
async def test_fee_pay_async_requires_gas_station_config_when_not_local() -> None:
    config = replace(TESTNET_CONFIG, gas_station_api_key=None, gas_station_url=None)
    with pytest.raises(ValueError, match="Either gas_station_api_key or gas_station_url"):
        await submit_fee_paid_transaction(config, SimpleNamespace(), SimpleNamespace())


def test_fee_pay_sync_prefers_local_mode_when_account_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"local": False}

    def fake_local(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        called["local"] = True
        return _pending_response("0xsync-local")

    def fake_gas_station(*args: Any, **kwargs: Any) -> PendingTransactionResponse:
        raise AssertionError("gas station path should not be called when fee_payer_account is set")

    monkeypatch.setattr(fee_pay_module, "_submit_via_local_fee_payer_sync", fake_local)
    monkeypatch.setattr(fee_pay_module, "_submit_via_gas_station_api_sync", fake_gas_station)
    monkeypatch.setattr(fee_pay_module, "_submit_via_legacy_fee_payer_sync", fake_gas_station)

    config = replace(TESTNET_CONFIG, gas_station_api_key="api-key")
    response = submit_fee_paid_transaction_sync(
        config,
        SimpleNamespace(),
        SimpleNamespace(),
        fee_payer_account=object(),
    )
    assert response.hash == "0xsync-local"
    assert called["local"] is True


@pytest.mark.asyncio
async def test_local_fee_payer_async_submits_to_fullnode(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_txn = SimpleNamespace(
        sender="0x111",
        sequence_number=7,
        max_gas_amount=200_000,
        gas_unit_price=2,
        expiration_timestamps_secs=999,
    )
    transaction = SimpleNamespace(
        raw_transaction=raw_txn,
        fee_payer_address=AccountAddress.from_str("0x2"),
    )
    client = RecordingAsyncClient(FakeResponse(payload={"hash": "0xabc"}))
    fee_payer_account = Account.generate()

    monkeypatch.setattr(
        fee_pay_module,
        "_build_fee_payer_signed_transaction_bytes",
        lambda *_args: b"signed-bytes",
    )

    response = await submit_fee_paid_transaction(
        TESTNET_CONFIG,
        transaction,
        SimpleNamespace(),
        fee_payer_account=fee_payer_account,
        client=client,
        txn_submit_timeout=1.5,
    )

    assert response.hash == "0xabc"
    assert response.sender == "0x111"
    assert response.sequence_number == "7"
    assert response.max_gas_amount == "200000"
    assert response.gas_unit_price == "2"
    assert response.expiration_timestamp_secs == "999"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == f"{TESTNET_CONFIG.fullnode_url}/transactions"
    assert call["content"] == b"signed-bytes"
    assert call["headers"]["Content-Type"] == "application/x.aptos.signed_transaction+bcs"
    assert call["timeout"] == 1.5


def test_local_fee_payer_sync_submits_to_fullnode(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_txn = SimpleNamespace(
        sender="0x111",
        sequence_number=7,
        max_gas_amount=200_000,
        gas_unit_price=2,
        expiration_timestamps_secs=999,
    )
    transaction = SimpleNamespace(
        raw_transaction=raw_txn,
        fee_payer_address=AccountAddress.from_str("0x2"),
    )
    client = RecordingSyncClient(FakeResponse(payload={"hash": "0xsync-abc"}))
    fee_payer_account = Account.generate()

    monkeypatch.setattr(
        fee_pay_module,
        "_build_fee_payer_signed_transaction_bytes",
        lambda *_args: b"sync-signed-bytes",
    )

    response = submit_fee_paid_transaction_sync(
        TESTNET_CONFIG,
        transaction,
        SimpleNamespace(),
        fee_payer_account=fee_payer_account,
        client=client,
        txn_submit_timeout=2.5,
    )

    assert response.hash == "0xsync-abc"
    assert response.sender == "0x111"
    assert response.sequence_number == "7"
    assert response.max_gas_amount == "200000"
    assert response.gas_unit_price == "2"
    assert response.expiration_timestamp_secs == "999"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == f"{TESTNET_CONFIG.fullnode_url}/transactions"
    assert call["content"] == b"sync-signed-bytes"
    assert call["headers"]["Content-Type"] == "application/x.aptos.signed_transaction+bcs"
    assert call["timeout"] == 2.5
