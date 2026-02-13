from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import httpx
from aptos_sdk.bcs import Serializer
from pydantic import BaseModel

if TYPE_CHECKING:
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
    client: httpx.AsyncClient | None = None,
) -> PendingTransactionResponse:
    if config.gas_station_api_key:
        return await _submit_via_gas_station_api(
            config,
            transaction,
            sender_authenticator,
            client=client,
        )

    if config.gas_station_url:
        return await _submit_via_legacy_fee_payer(
            config,
            transaction,
            sender_authenticator,
            client=client,
        )

    raise ValueError("Either gas_station_api_key or gas_station_url must be provided")


def submit_fee_paid_transaction_sync(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    client: httpx.Client | None = None,
) -> PendingTransactionResponse:
    if config.gas_station_api_key:
        return _submit_via_gas_station_api_sync(
            config,
            transaction,
            sender_authenticator,
            client=client,
        )

    if config.gas_station_url:
        return _submit_via_legacy_fee_payer_sync(
            config,
            transaction,
            sender_authenticator,
            client=client,
        )

    raise ValueError("Either gas_station_api_key or gas_station_url must be provided")


async def _submit_via_gas_station_api(
    config: DecibelConfig,
    transaction: SimpleTransaction,
    sender_authenticator: AccountAuthenticator,
    *,
    client: httpx.AsyncClient | None = None,
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

    if client is not None:
        response = await client.post(url, json=body, headers=headers)
    else:
        async with httpx.AsyncClient() as temp_client:
            response = await temp_client.post(url, json=body, headers=headers)

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

    if client is not None:
        response = client.post(url, json=body, headers=headers)
    else:
        with httpx.Client() as temp_client:
            response = temp_client.post(url, json=body, headers=headers)

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
        response = await client.post(url, json=body, headers=headers)
    else:
        async with httpx.AsyncClient() as temp_client:
            response = await temp_client.post(url, json=body, headers=headers)

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
        response = client.post(url, json=body, headers=headers)
    else:
        with httpx.Client() as temp_client:
            response = temp_client.post(url, json=body, headers=headers)

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


def _get_default_gas_station_url(config: DecibelConfig) -> str:
    from ._constants import Network

    if config.network == Network.TESTNET:
        return "https://api.testnet.aptoslabs.com/gs/v1"

    if config.chain_id == 208:
        return "https://api.netna.aptoslabs.com/gs/v1"

    if config.gas_station_url:
        return config.gas_station_url

    raise ValueError(
        "gas_station_url must be provided for custom networks when using gas_station_api_key"
    )
