from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import httpx
from aptos_sdk.async_client import RestClient
from aptos_sdk.authenticator import (
    AccountAuthenticator,
    Authenticator,
    Ed25519Authenticator,
    FeePayerAuthenticator,
)
from aptos_sdk.bcs import Serializer
from aptos_sdk.ed25519 import PublicKey as Ed25519PublicKey
from aptos_sdk.ed25519 import Signature as Ed25519Signature
from aptos_sdk.transactions import FeePayerRawTransaction, SignedTransaction

from ._fee_pay import (
    PendingTransactionResponse,
    submit_fee_paid_transaction,
    submit_fee_paid_transaction_sync,
)
from ._transaction_builder import build_simple_transaction_sync
from ._utils import generate_random_replay_protection_nonce, get_primary_subaccount_addr
from .abi import AbiRegistry

if TYPE_CHECKING:
    from aptos_sdk.account import Account
    from aptos_sdk.account_address import AccountAddress

    from ._constants import DecibelConfig
    from ._gas_price_manager import GasPriceManager, GasPriceManagerSync
    from ._transaction_builder import InputEntryFunctionData, SimpleTransaction
    from .abi import MoveFunction

__all__ = [
    "BaseSDK",
    "BaseSDKOptions",
    "BaseSDKSync",
]

logger = logging.getLogger(__name__)

DEFAULT_MAX_GAS_AMOUNT = 200_000
DEFAULT_GAS_ESTIMATE = 100
MAX_GAS_UNITS_LIMIT = 2_000_000


@dataclass
class BaseSDKOptions:
    skip_simulate: bool = False
    no_fee_payer: bool = False
    node_api_key: str | None = None
    gas_price_manager: GasPriceManager | None = None
    time_delta_ms: int = 0


@dataclass
class BaseSDKOptionsSync:
    skip_simulate: bool = False
    no_fee_payer: bool = False
    node_api_key: str | None = None
    gas_price_manager: GasPriceManagerSync | None = None
    time_delta_ms: int = 0
    http_client: httpx.Client | None = None


class BaseSDK:
    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptions | None = None,
    ) -> None:
        self._config = config
        self._account = account
        self._chain_id = config.chain_id
        self._abi_registry = AbiRegistry(chain_id=config.chain_id)
        self._aptos = RestClient(config.fullnode_url)

        opts = opts or BaseSDKOptions()
        self._skip_simulate = opts.skip_simulate
        self._no_fee_payer = opts.no_fee_payer
        self._node_api_key = opts.node_api_key
        self._gas_price_manager = opts.gas_price_manager
        self._time_delta_ms = opts.time_delta_ms

        if config.chain_id is None:
            logger.warning(
                "Using default ABI for unknown chain_id, "
                "this might cause issues with the transaction builder"
            )

    @property
    def aptos(self) -> RestClient:
        return self._aptos

    @property
    def config(self) -> DecibelConfig:
        return self._config

    @property
    def account(self) -> Account:
        return self._account

    @property
    def skip_simulate(self) -> bool:
        return self._skip_simulate

    @property
    def no_fee_payer(self) -> bool:
        return self._no_fee_payer

    @property
    def time_delta_ms(self) -> int:
        return self._time_delta_ms

    @time_delta_ms.setter
    def time_delta_ms(self, value: int) -> None:
        self._time_delta_ms = value

    def _get_abi(self, function_id: str) -> MoveFunction | None:
        return self._abi_registry.get_function(function_id)

    async def build_tx(
        self,
        data: InputEntryFunctionData,
        sender: AccountAddress,
        *,
        max_gas_amount: int | None = None,
        gas_unit_price: int | None = None,
    ) -> SimpleTransaction:
        function_abi = self._get_abi(data.function)

        nonce = generate_random_replay_protection_nonce()
        if nonce is None:
            raise ValueError("Unable to generate replay protection nonce")

        if function_abi is None or self._chain_id is None:
            raise ValueError(
                f"Cannot build transaction: missing ABI for {data.function} or chain_id is None"
            )

        if gas_unit_price is None:
            if self._gas_price_manager is not None:
                cached_price = self._gas_price_manager.get_gas_price()
                if cached_price is not None:
                    gas_unit_price = cached_price
                else:
                    gas_unit_price = await self._gas_price_manager.fetch_and_set_gas_price()
            else:
                gas_unit_price = await self._fetch_gas_price_estimation()

        return build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=self._chain_id,
            gas_unit_price=gas_unit_price,
            abi=function_abi,
            with_fee_payer=not self._no_fee_payer,
            replay_protection_nonce=nonce,
            time_delta_ms=self._time_delta_ms,
            max_gas_amount=max_gas_amount or DEFAULT_MAX_GAS_AMOUNT,
        )

    async def submit_tx(
        self,
        transaction: SimpleTransaction,
        sender_authenticator: AccountAuthenticator,
    ) -> PendingTransactionResponse:
        if self._no_fee_payer:
            return await self._submit_direct(transaction, sender_authenticator)
        return await submit_fee_paid_transaction(
            self._config,
            transaction,
            sender_authenticator,
        )

    async def _send_tx(
        self,
        payload: InputEntryFunctionData,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        signer = account_override if account_override is not None else self._account
        sender = signer.address()

        transaction = await self.build_tx(payload, sender)

        if not self._skip_simulate:
            sim_result = await self._simulate_transaction(transaction)

            max_gas_amount_str = sim_result.get("max_gas_amount")
            gas_unit_price_str = sim_result.get("gas_unit_price")

            if max_gas_amount_str is None or gas_unit_price_str is None:
                raise ValueError("Transaction simulation returned no results")

            simulated_max_gas = int(max_gas_amount_str)
            simulated_gas_price = int(gas_unit_price_str)

            max_gas_amount = min(
                max(simulated_max_gas * 2, DEFAULT_MAX_GAS_AMOUNT),
                MAX_GAS_UNITS_LIMIT,
            )
            gas_unit_price = max(simulated_gas_price, 1)

            transaction = await self.build_tx(
                payload,
                sender,
                max_gas_amount=max_gas_amount,
                gas_unit_price=gas_unit_price,
            )

        sender_authenticator = self._sign_transaction(signer, transaction)

        pending_tx = await self.submit_tx(transaction, sender_authenticator)

        return await self._wait_for_transaction(pending_tx.hash)

    def _sign_transaction(
        self,
        signer: Account,
        transaction: SimpleTransaction,
    ) -> AccountAuthenticator:
        raw_txn = transaction.raw_transaction

        if transaction.fee_payer_address is not None:
            fee_payer_txn = FeePayerRawTransaction(
                raw_transaction=raw_txn,
                secondary_signers=[],
                fee_payer=transaction.fee_payer_address,
            )
            return fee_payer_txn.sign(signer.private_key)
        else:
            return raw_txn.sign(signer.private_key)

    async def _fetch_gas_price_estimation(self) -> int:
        url = f"{self._config.fullnode_url}/estimate_gas_price"
        headers = self._build_node_headers()

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        if not response.is_success:
            raise ValueError(f"Failed to fetch gas price: {response.status_code} - {response.text}")

        data = cast("dict[str, Any]", response.json())
        return int(data.get("gas_estimate", DEFAULT_GAS_ESTIMATE))

    async def _simulate_transaction(
        self,
        transaction: SimpleTransaction,
    ) -> dict[str, Any]:
        url = f"{self._config.fullnode_url}/transactions/simulate"
        headers = self._build_node_headers()
        headers["Content-Type"] = "application/x.aptos.signed_transaction+bcs"

        bcs_bytes = self._serialize_for_simulation(transaction)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=bcs_bytes,
                headers=headers,
                params={"estimate_max_gas_amount": "true", "estimate_gas_unit_price": "true"},
            )

        if not response.is_success:
            raise ValueError(
                f"Transaction simulation failed: {response.status_code} - {response.text}"
            )

        data: list[dict[str, Any]] | dict[str, Any] = response.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]

        raise ValueError("Transaction simulation returned empty results")

    async def _submit_direct(
        self,
        transaction: SimpleTransaction,
        sender_authenticator: AccountAuthenticator,
    ) -> PendingTransactionResponse:
        url = f"{self._config.fullnode_url}/transactions"
        headers = self._build_node_headers()
        headers["Content-Type"] = "application/x.aptos.signed_transaction+bcs"

        bcs_bytes = self._serialize_signed_transaction(transaction, sender_authenticator)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=bcs_bytes, headers=headers)

        if not response.is_success:
            raise ValueError(
                f"Transaction submission failed: {response.status_code} - {response.text}"
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

    async def _wait_for_transaction(
        self,
        tx_hash: str,
        timeout_secs: float = 30.0,
        poll_interval_secs: float = 1.0,
    ) -> dict[str, Any]:
        url = f"{self._config.fullnode_url}/transactions/by_hash/{tx_hash}"
        headers = self._build_node_headers()
        start_time = time.time()

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(url, headers=headers)

                if response.is_success:
                    data = cast("dict[str, Any]", response.json())
                    tx_type = data.get("type")
                    if tx_type == "pending_transaction":
                        pass
                    elif data.get("success") is True:
                        return data
                    elif data.get("success") is False:
                        vm_status = data.get("vm_status", "Unknown error")
                        raise ValueError(f"Transaction failed: {vm_status}")

                if time.time() - start_time > timeout_secs:
                    raise TimeoutError(
                        f"Transaction {tx_hash} did not complete within {timeout_secs}s"
                    )

                await self._async_sleep(poll_interval_secs)

    async def _async_sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    def _build_node_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._node_api_key:
            headers["x-api-key"] = self._node_api_key
        return headers

    def _serialize_for_simulation(self, transaction: SimpleTransaction) -> bytes:
        zero_signature = Ed25519Signature(b"\x00" * 64)
        sender_public_key = cast("Ed25519PublicKey", self._account.public_key())
        sender_auth = AccountAuthenticator(Ed25519Authenticator(sender_public_key, zero_signature))

        raw_txn = transaction.raw_transaction

        if transaction.fee_payer_address is not None:
            fee_payer_auth = AccountAuthenticator(
                Ed25519Authenticator(sender_public_key, zero_signature)
            )
            fee_payer_authenticator = FeePayerAuthenticator(
                sender=sender_auth,
                secondary_signers=[],
                fee_payer=(transaction.fee_payer_address, fee_payer_auth),
            )
            authenticator = Authenticator(fee_payer_authenticator)
        else:
            authenticator = Authenticator(Ed25519Authenticator(sender_public_key, zero_signature))

        signed_txn = SignedTransaction(raw_txn, authenticator)
        return signed_txn.bytes()

    def _serialize_signed_transaction(
        self,
        transaction: SimpleTransaction,
        sender_authenticator: AccountAuthenticator,
    ) -> bytes:
        serializer = Serializer()

        transaction.raw_transaction.serialize(serializer)

        sender_authenticator.serialize(serializer)

        return serializer.output()

    def get_primary_subaccount_address(self, addr: AccountAddress | str) -> str:
        return get_primary_subaccount_addr(
            addr,
            self._config.compat_version,
            self._config.deployment.package,
        )


class BaseSDKSync:
    def __init__(
        self,
        config: DecibelConfig,
        account: Account,
        opts: BaseSDKOptionsSync | None = None,
    ) -> None:
        self._config = config
        self._account = account
        self._chain_id = config.chain_id
        self._abi_registry = AbiRegistry(chain_id=config.chain_id)

        opts = opts or BaseSDKOptionsSync()
        self._skip_simulate = opts.skip_simulate
        self._no_fee_payer = opts.no_fee_payer
        self._node_api_key = opts.node_api_key
        self._gas_price_manager = opts.gas_price_manager
        self._time_delta_ms = opts.time_delta_ms
        self._http_client = opts.http_client

        if config.chain_id is None:
            logger.warning(
                "Using default ABI for unknown chain_id, "
                "this might cause issues with the transaction builder"
            )

    @property
    def config(self) -> DecibelConfig:
        return self._config

    @property
    def account(self) -> Account:
        return self._account

    @property
    def skip_simulate(self) -> bool:
        return self._skip_simulate

    @property
    def no_fee_payer(self) -> bool:
        return self._no_fee_payer

    @property
    def time_delta_ms(self) -> int:
        return self._time_delta_ms

    @time_delta_ms.setter
    def time_delta_ms(self, value: int) -> None:
        self._time_delta_ms = value

    def _get_abi(self, function_id: str) -> MoveFunction | None:
        return self._abi_registry.get_function(function_id)

    def build_tx(
        self,
        data: InputEntryFunctionData,
        sender: AccountAddress,
        *,
        max_gas_amount: int | None = None,
        gas_unit_price: int | None = None,
    ) -> SimpleTransaction:
        function_abi = self._get_abi(data.function)

        nonce = generate_random_replay_protection_nonce()
        if nonce is None:
            raise ValueError("Unable to generate replay protection nonce")

        if function_abi is None or self._chain_id is None:
            raise ValueError(
                f"Cannot build transaction: missing ABI for {data.function} or chain_id is None"
            )

        if gas_unit_price is None:
            if self._gas_price_manager is not None:
                cached_price = self._gas_price_manager.get_gas_price()
                if cached_price is not None:
                    gas_unit_price = cached_price
                else:
                    gas_unit_price = self._gas_price_manager.fetch_and_set_gas_price()
            else:
                gas_unit_price = self._fetch_gas_price_estimation()

        return build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=self._chain_id,
            gas_unit_price=gas_unit_price,
            abi=function_abi,
            with_fee_payer=not self._no_fee_payer,
            replay_protection_nonce=nonce,
            time_delta_ms=self._time_delta_ms,
            max_gas_amount=max_gas_amount or DEFAULT_MAX_GAS_AMOUNT,
        )

    def submit_tx(
        self,
        transaction: SimpleTransaction,
        sender_authenticator: AccountAuthenticator,
    ) -> PendingTransactionResponse:
        if self._no_fee_payer:
            return self._submit_direct(transaction, sender_authenticator)
        return submit_fee_paid_transaction_sync(
            self._config,
            transaction,
            sender_authenticator,
        )

    def _send_tx(
        self,
        payload: InputEntryFunctionData,
        account_override: Account | None = None,
    ) -> dict[str, Any]:
        signer = account_override if account_override is not None else self._account
        sender = signer.address()

        transaction = self.build_tx(payload, sender)

        if not self._skip_simulate:
            sim_result = self._simulate_transaction(transaction)

            max_gas_amount_str = sim_result.get("max_gas_amount")
            gas_unit_price_str = sim_result.get("gas_unit_price")

            if max_gas_amount_str is None or gas_unit_price_str is None:
                raise ValueError("Transaction simulation returned no results")

            simulated_max_gas = int(max_gas_amount_str)
            simulated_gas_price = int(gas_unit_price_str)

            max_gas_amount = min(
                max(simulated_max_gas * 2, DEFAULT_MAX_GAS_AMOUNT),
                MAX_GAS_UNITS_LIMIT,
            )
            gas_unit_price = max(simulated_gas_price, 1)

            transaction = self.build_tx(
                payload,
                sender,
                max_gas_amount=max_gas_amount,
                gas_unit_price=gas_unit_price,
            )

        sender_authenticator = self._sign_transaction(signer, transaction)

        pending_tx = self.submit_tx(transaction, sender_authenticator)

        return self._wait_for_transaction(pending_tx.hash)

    def _sign_transaction(
        self,
        signer: Account,
        transaction: SimpleTransaction,
    ) -> AccountAuthenticator:
        raw_txn = transaction.raw_transaction

        if transaction.fee_payer_address is not None:
            fee_payer_txn = FeePayerRawTransaction(
                raw_transaction=raw_txn,
                secondary_signers=[],
                fee_payer=transaction.fee_payer_address,
            )
            return fee_payer_txn.sign(signer.private_key)
        else:
            return raw_txn.sign(signer.private_key)

    def _fetch_gas_price_estimation(self) -> int:
        url = f"{self._config.fullnode_url}/estimate_gas_price"
        headers = self._build_node_headers()

        def make_request(client: httpx.Client) -> int:
            response = client.get(url, headers=headers)
            if not response.is_success:
                raise ValueError(
                    f"Failed to fetch gas price: {response.status_code} - {response.text}"
                )
            data = cast("dict[str, Any]", response.json())
            return int(data.get("gas_estimate", DEFAULT_GAS_ESTIMATE))

        if self._http_client is not None:
            return make_request(self._http_client)
        with httpx.Client() as client:
            return make_request(client)

    def _simulate_transaction(
        self,
        transaction: SimpleTransaction,
    ) -> dict[str, Any]:
        url = f"{self._config.fullnode_url}/transactions/simulate"
        headers = self._build_node_headers()
        headers["Content-Type"] = "application/x.aptos.signed_transaction+bcs"
        bcs_bytes = self._serialize_for_simulation(transaction)

        def make_request(client: httpx.Client) -> dict[str, Any]:
            response = client.post(
                url,
                content=bcs_bytes,
                headers=headers,
                params={"estimate_max_gas_amount": "true", "estimate_gas_unit_price": "true"},
            )
            if not response.is_success:
                raise ValueError(
                    f"Transaction simulation failed: {response.status_code} - {response.text}"
                )
            data: list[dict[str, Any]] | dict[str, Any] = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            raise ValueError("Transaction simulation returned empty results")

        if self._http_client is not None:
            return make_request(self._http_client)
        with httpx.Client() as client:
            return make_request(client)

    def _submit_direct(
        self,
        transaction: SimpleTransaction,
        sender_authenticator: AccountAuthenticator,
    ) -> PendingTransactionResponse:
        url = f"{self._config.fullnode_url}/transactions"
        headers = self._build_node_headers()
        headers["Content-Type"] = "application/x.aptos.signed_transaction+bcs"
        bcs_bytes = self._serialize_signed_transaction(transaction, sender_authenticator)

        def make_request(client: httpx.Client) -> PendingTransactionResponse:
            response = client.post(url, content=bcs_bytes, headers=headers)
            if not response.is_success:
                raise ValueError(
                    f"Transaction submission failed: {response.status_code} - {response.text}"
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

        if self._http_client is not None:
            return make_request(self._http_client)
        with httpx.Client() as client:
            return make_request(client)

    def _wait_for_transaction(
        self,
        tx_hash: str,
        timeout_secs: float = 30.0,
        poll_interval_secs: float = 1.0,
    ) -> dict[str, Any]:
        url = f"{self._config.fullnode_url}/transactions/by_hash/{tx_hash}"
        headers = self._build_node_headers()
        start_time = time.time()

        def poll_loop(client: httpx.Client) -> dict[str, Any]:
            while True:
                response = client.get(url, headers=headers)
                if response.is_success:
                    data = cast("dict[str, Any]", response.json())
                    tx_type = data.get("type")
                    if tx_type == "pending_transaction":
                        pass
                    elif data.get("success") is True:
                        return data
                    elif data.get("success") is False:
                        vm_status = data.get("vm_status", "Unknown error")
                        raise ValueError(f"Transaction failed: {vm_status}")
                if time.time() - start_time > timeout_secs:
                    raise TimeoutError(
                        f"Transaction {tx_hash} did not complete within {timeout_secs}s"
                    )
                time.sleep(poll_interval_secs)

        if self._http_client is not None:
            return poll_loop(self._http_client)
        with httpx.Client() as client:
            return poll_loop(client)

    def _build_node_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._node_api_key:
            headers["x-api-key"] = self._node_api_key
        return headers

    def _serialize_for_simulation(self, transaction: SimpleTransaction) -> bytes:
        zero_signature = Ed25519Signature(b"\x00" * 64)
        sender_public_key = cast("Ed25519PublicKey", self._account.public_key())
        sender_auth = AccountAuthenticator(Ed25519Authenticator(sender_public_key, zero_signature))

        raw_txn = transaction.raw_transaction

        if transaction.fee_payer_address is not None:
            fee_payer_auth = AccountAuthenticator(
                Ed25519Authenticator(sender_public_key, zero_signature)
            )
            fee_payer_authenticator = FeePayerAuthenticator(
                sender=sender_auth,
                secondary_signers=[],
                fee_payer=(transaction.fee_payer_address, fee_payer_auth),
            )
            authenticator = Authenticator(fee_payer_authenticator)
        else:
            authenticator = Authenticator(Ed25519Authenticator(sender_public_key, zero_signature))

        signed_txn = SignedTransaction(raw_txn, authenticator)
        return signed_txn.bytes()

    def _serialize_signed_transaction(
        self,
        transaction: SimpleTransaction,
        sender_authenticator: AccountAuthenticator,
    ) -> bytes:
        serializer = Serializer()

        transaction.raw_transaction.serialize(serializer)

        sender_authenticator.serialize(serializer)

        return serializer.output()

    def get_primary_subaccount_address(self, addr: AccountAddress | str) -> str:
        return get_primary_subaccount_addr(
            addr,
            self._config.compat_version,
            self._config.deployment.package,
        )
