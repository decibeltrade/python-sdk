from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import httpx
from aptos_sdk.authenticator import Authenticator, FeePayerAuthenticator
from aptos_sdk.bcs import Serializer
from aptos_sdk.transactions import FeePayerRawTransaction, SignedTransaction
from pydantic import BaseModel

if TYPE_CHECKING:
    from aptos_sdk.account import Account
    from aptos_sdk.authenticator import AccountAuthenticator

    from ._constants import DecibelConfig
    from ._transaction_builder import SimpleTransaction

__all__ = [
    "PendingTransactionResponse",
    "submit_fee_paid_transaction",
    "submit_fee_paid_transaction_sync",
]


class PendingTransactionResponse(BaseModel):
    hash: str
    sender: str
    sequence_number: str
    max_gas_amount: str
    gas_unit_price: str
    expiration_timestamp_secs: str


async def submit_fee_paid_transaction(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    fee_payer_account: Account | None = None,
    node_api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    if fee_payer_account is not None:
        return await _submit_via_local_fee_payer(
            config,
            transaction,
            sender_authenticator,
            fee_payer_account=fee_payer_account,
            node_api_key=node_api_key,
            client=client,
            txn_submit_timeout=txn_submit_timeout,
        )

    if config.gas_station_api_key:
        return await _submit_via_gas_station_api(
            config,
            transaction,
            sender_authenticator,
            client=client,
            txn_submit_timeout=txn_submit_timeout,
        )

    if config.gas_station_url:
        return await _submit_via_legacy_fee_payer(
            config,
            transaction,
            sender_authenticator,
            client=client,
            txn_submit_timeout=txn_submit_timeout,
        )

    raise ValueError("Either gas_station_api_key or gas_station_url must be provided")


def submit_fee_paid_transaction_sync(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    fee_payer_account: Account | None = None,
    node_api_key: str | None = None,
    client: httpx.Client | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    if fee_payer_account is not None:
        return _submit_via_local_fee_payer_sync(
            config,
            transaction,
            sender_authenticator,
            fee_payer_account=fee_payer_account,
            node_api_key=node_api_key,
            client=client,
            txn_submit_timeout=txn_submit_timeout,
        )

    if config.gas_station_api_key:
        return _submit_via_gas_station_api_sync(
            config,
            transaction,
            sender_authenticator,
            client=client,
            txn_submit_timeout=txn_submit_timeout,
        )

    if config.gas_station_url:
        return _submit_via_legacy_fee_payer_sync(
            config,
            transaction,
            sender_authenticator,
            client=client,
            txn_submit_timeout=txn_submit_timeout,
        )

    raise ValueError("Either gas_station_api_key or gas_station_url must be provided")


async def _submit_via_gas_station_api(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    client: httpx.AsyncClient | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    base_url = _get_default_gas_station_url(config)
    url = f"{base_url}/api/transaction/signAndSubmit"

    raw_txn = transaction.raw_transaction

    txn_serializer = Serializer()
    raw_txn.serialize(txn_serializer)
    if transaction.fee_payer_address is None:
        txn_serializer.bool(False)
    else:
        txn_serializer.bool(True)
        transaction.fee_payer_address.serialize(txn_serializer)
    transaction_bytes = list(txn_serializer.output())

    auth_serializer = Serializer()
    sender_authenticator.serialize(auth_serializer)
    authenticator_bytes = list(auth_serializer.output())

    body = {
        "transactionBytes": transaction_bytes,
        "senderAuth": authenticator_bytes,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.gas_station_api_key}",
    }

    async def _do_submit(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(url, json=body, headers=headers, timeout=txn_submit_timeout)

    if client is not None:
        response = await _do_submit(client)
    else:
        async with httpx.AsyncClient() as temp_client:
            response = await _do_submit(temp_client)

    if not response.is_success:
        raise ValueError(f"Gas station API error: {response.status_code} - {response.text}")

    data = response.json()
    transaction_hash = data.get("transactionHash", data.get("hash", ""))

    return PendingTransactionResponse(
        hash=transaction_hash,
        sender=str(raw_txn.sender),
        sequence_number=str(raw_txn.sequence_number),
        max_gas_amount=str(raw_txn.max_gas_amount),
        gas_unit_price=str(raw_txn.gas_unit_price),
        expiration_timestamp_secs=str(raw_txn.expiration_timestamps_secs),
    )


def _submit_via_gas_station_api_sync(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    client: httpx.Client | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    base_url = _get_default_gas_station_url(config)
    url = f"{base_url}/api/transaction/signAndSubmit"

    raw_txn = transaction.raw_transaction

    txn_serializer = Serializer()
    raw_txn.serialize(txn_serializer)
    if transaction.fee_payer_address is None:
        txn_serializer.bool(False)
    else:
        txn_serializer.bool(True)
        transaction.fee_payer_address.serialize(txn_serializer)
    transaction_bytes = list(txn_serializer.output())

    auth_serializer = Serializer()
    sender_authenticator.serialize(auth_serializer)
    authenticator_bytes = list(auth_serializer.output())

    body = {
        "transactionBytes": transaction_bytes,
        "senderAuth": authenticator_bytes,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.gas_station_api_key}",
    }

    def _do_submit(c: httpx.Client) -> httpx.Response:
        return c.post(url, json=body, headers=headers, timeout=txn_submit_timeout)

    if client is not None:
        response = _do_submit(client)
    else:
        with httpx.Client() as temp_client:
            response = _do_submit(temp_client)

    if not response.is_success:
        raise ValueError(f"Gas station API error: {response.status_code} - {response.text}")

    data = response.json()
    transaction_hash = data.get("transactionHash", data.get("hash", ""))

    return PendingTransactionResponse(
        hash=transaction_hash,
        sender=str(raw_txn.sender),
        sequence_number=str(raw_txn.sequence_number),
        max_gas_amount=str(raw_txn.max_gas_amount),
        gas_unit_price=str(raw_txn.gas_unit_price),
        expiration_timestamp_secs=str(raw_txn.expiration_timestamps_secs),
    )


async def _submit_via_legacy_fee_payer(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    client: httpx.AsyncClient | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    url = f"{config.gas_station_url}/transactions"

    auth_serializer = Serializer()
    sender_authenticator.serialize(auth_serializer)
    signature_bytes = list(auth_serializer.output())

    txn_serializer = Serializer()
    transaction.raw_transaction.serialize(txn_serializer)
    transaction_bytes = list(txn_serializer.output())

    body = {
        "signature": signature_bytes,
        "transaction": transaction_bytes,
    }

    headers = {"Content-Type": "application/json"}

    if client is not None:
        response = await client.post(url, json=body, headers=headers, timeout=txn_submit_timeout)
    else:
        async with httpx.AsyncClient() as temp_client:
            response = await temp_client.post(
                url, json=body, headers=headers, timeout=txn_submit_timeout
            )

    # TODO: Improve error handling
    if not response.is_success:
        raise ValueError(f"Fee payer error: {response.status_code} - {response.text}")

    data = cast("dict[str, Any]", response.json())
    return PendingTransactionResponse(
        hash=str(data.get("hash", "")),
        sender=str(data.get("sender", "")),
        sequence_number=str(data.get("sequence_number", "")),
        max_gas_amount=str(data.get("max_gas_amount", "")),
        gas_unit_price=str(data.get("gas_unit_price", "")),
        expiration_timestamp_secs=str(data.get("expiration_timestamp_secs", "")),
    )


def _submit_via_legacy_fee_payer_sync(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    client: httpx.Client | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    url = f"{config.gas_station_url}/transactions"

    auth_serializer = Serializer()
    sender_authenticator.serialize(auth_serializer)
    signature_bytes = list(auth_serializer.output())

    txn_serializer = Serializer()
    transaction.raw_transaction.serialize(txn_serializer)
    transaction_bytes = list(txn_serializer.output())

    body = {
        "signature": signature_bytes,
        "transaction": transaction_bytes,
    }

    headers = {"Content-Type": "application/json"}

    if client is not None:
        response = client.post(url, json=body, headers=headers, timeout=txn_submit_timeout)
    else:
        with httpx.Client() as temp_client:
            response = temp_client.post(url, json=body, headers=headers, timeout=txn_submit_timeout)

    # TODO: Improve error handling
    if not response.is_success:
        raise ValueError(f"Fee payer error: {response.status_code} - {response.text}")

    data = cast("dict[str, Any]", response.json())
    return PendingTransactionResponse(
        hash=str(data.get("hash", "")),
        sender=str(data.get("sender", "")),
        sequence_number=str(data.get("sequence_number", "")),
        max_gas_amount=str(data.get("max_gas_amount", "")),
        gas_unit_price=str(data.get("gas_unit_price", "")),
        expiration_timestamp_secs=str(data.get("expiration_timestamp_secs", "")),
    )


async def _submit_via_local_fee_payer(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    fee_payer_account: Account,
    node_api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    url = f"{config.fullnode_url}/transactions"
    headers = {"Content-Type": "application/x.aptos.signed_transaction+bcs"}
    if node_api_key:
        headers["x-api-key"] = node_api_key
    bcs_bytes = _build_fee_payer_signed_transaction_bytes(
        transaction,
        sender_authenticator,
        fee_payer_account,
    )

    if client is not None:
        response = await client.post(
            url,
            content=bcs_bytes,
            headers=headers,
            timeout=txn_submit_timeout,
        )
    else:
        async with httpx.AsyncClient() as temp_client:
            response = await temp_client.post(
                url,
                content=bcs_bytes,
                headers=headers,
                timeout=txn_submit_timeout,
            )

    if not response.is_success:
        raise ValueError(
            f"Local fee payer submission failed: {response.status_code} - {response.text}"
        )

    data = cast("dict[str, Any]", response.json())
    raw_txn = transaction.raw_transaction
    return PendingTransactionResponse(
        hash=str(data.get("hash", "")),
        sender=str(raw_txn.sender),
        sequence_number=str(raw_txn.sequence_number),
        max_gas_amount=str(raw_txn.max_gas_amount),
        gas_unit_price=str(raw_txn.gas_unit_price),
        expiration_timestamp_secs=str(raw_txn.expiration_timestamps_secs),
    )


def _submit_via_local_fee_payer_sync(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    fee_payer_account: Account,
    node_api_key: str | None = None,
    client: httpx.Client | None = None,
    txn_submit_timeout: float | None = None,
) -> PendingTransactionResponse:
    url = f"{config.fullnode_url}/transactions"
    headers = {"Content-Type": "application/x.aptos.signed_transaction+bcs"}
    if node_api_key:
        headers["x-api-key"] = node_api_key
    bcs_bytes = _build_fee_payer_signed_transaction_bytes(
        transaction,
        sender_authenticator,
        fee_payer_account,
    )

    if client is not None:
        response = client.post(
            url,
            content=bcs_bytes,
            headers=headers,
            timeout=txn_submit_timeout,
        )
    else:
        with httpx.Client() as temp_client:
            response = temp_client.post(
                url,
                content=bcs_bytes,
                headers=headers,
                timeout=txn_submit_timeout,
            )

    if not response.is_success:
        raise ValueError(
            f"Local fee payer submission failed: {response.status_code} - {response.text}"
        )

    data = cast("dict[str, Any]", response.json())
    raw_txn = transaction.raw_transaction
    return PendingTransactionResponse(
        hash=str(data.get("hash", "")),
        sender=str(raw_txn.sender),
        sequence_number=str(raw_txn.sequence_number),
        max_gas_amount=str(raw_txn.max_gas_amount),
        gas_unit_price=str(raw_txn.gas_unit_price),
        expiration_timestamp_secs=str(raw_txn.expiration_timestamps_secs),
    )


def _build_fee_payer_signed_transaction_bytes(
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    fee_payer_account: Account,
) -> bytes:
    if transaction.fee_payer_address is None:
        raise ValueError("transaction.fee_payer_address must be set for local fee payer submission")

    fee_payer_address = fee_payer_account.address()
    if transaction.fee_payer_address != fee_payer_address:
        raise ValueError("transaction.fee_payer_address does not match fee_payer_account")

    fee_payer_raw_txn = FeePayerRawTransaction(
        raw_transaction=transaction.raw_transaction,
        secondary_signers=[],
        fee_payer=fee_payer_address,
    )
    fee_payer_authenticator = fee_payer_raw_txn.sign(fee_payer_account.private_key)

    authenticator = Authenticator(
        FeePayerAuthenticator(
            sender=sender_authenticator,
            secondary_signers=[],
            fee_payer=(fee_payer_address, fee_payer_authenticator),
        )
    )
    return SignedTransaction(transaction.raw_transaction, authenticator).bytes()


def _get_default_gas_station_url(config: DecibelConfig) -> str:
    from ._constants import Network

    if config.network == Network.TESTNET:
        return "https://api.testnet.aptoslabs.com/gs/v1"

    if config.gas_station_url:
        return config.gas_station_url

    raise ValueError(
        "gas_station_url must be provided for custom networks when using gas_station_api_key"
    )
