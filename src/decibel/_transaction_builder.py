from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from aptos_sdk.account_address import AccountAddress
from aptos_sdk.bcs import Deserializer, Serializer
from aptos_sdk.transactions import (
    EntryFunction,
    ModuleId,
    RawTransaction,
    TransactionPayload,
)
from aptos_sdk.type_tag import StructTag, TypeTag

if TYPE_CHECKING:
    from .abi import MoveFunction

__all__ = [
    "InputEntryFunctionData",
    "SimpleTransaction",
    "TransactionPayloadOrderless",
    "build_simple_transaction_sync",
    "generate_expire_timestamp",
]

DEADBEEF_SEQUENCE_NUMBER = 0xDEADBEEF

# BCS variant constants for orderless transaction payloads
_PAYLOAD_VARIANT_ORDERLESS = 4
_INNER_PAYLOAD_VARIANT_V1 = 0
_EXECUTABLE_VARIANT_ENTRY_FUNCTION = 1
_EXTRA_CONFIG_VARIANT_V1 = 0


class TransactionExtraConfigV1:
    """Extra configuration for orderless transactions containing replay protection nonce."""

    def __init__(
        self,
        multisig_address: AccountAddress | None = None,
        replay_protection_nonce: int | None = None,
    ) -> None:
        self.multisig_address = multisig_address
        self.replay_protection_nonce = replay_protection_nonce

    def serialize(self, serializer: Serializer) -> None:
        serializer.uleb128(_EXTRA_CONFIG_VARIANT_V1)

        if self.multisig_address is None:
            serializer.u8(0)
        else:
            serializer.u8(1)
            self.multisig_address.serialize(serializer)

        if self.replay_protection_nonce is None:
            serializer.u8(0)
        else:
            serializer.u8(1)
            serializer.u64(self.replay_protection_nonce)

    @staticmethod
    def deserialize(deserializer: Deserializer) -> TransactionExtraConfigV1:
        variant = deserializer.uleb128()
        if variant != _EXTRA_CONFIG_VARIANT_V1:
            raise ValueError(f"Unknown TransactionExtraConfig variant: {variant}")
        has_multisig = deserializer.u8() == 1
        multisig_address = AccountAddress.deserialize(deserializer) if has_multisig else None
        has_nonce = deserializer.u8() == 1
        nonce = deserializer.u64() if has_nonce else None
        return TransactionExtraConfigV1(multisig_address, nonce)


class TransactionExecutableEntryFunction:
    """Wrapper for entry function in orderless transactions."""

    def __init__(self, entry_function: EntryFunction) -> None:
        self.entry_function = entry_function

    def serialize(self, serializer: Serializer) -> None:
        serializer.uleb128(_EXECUTABLE_VARIANT_ENTRY_FUNCTION)
        self.entry_function.serialize(serializer)


class TransactionInnerPayloadV1:
    """Inner payload for orderless transactions containing executable and extra config."""

    def __init__(
        self,
        executable: TransactionExecutableEntryFunction,
        extra_config: TransactionExtraConfigV1,
    ) -> None:
        self.executable = executable
        self.extra_config = extra_config

    def serialize(self, serializer: Serializer) -> None:
        serializer.uleb128(_INNER_PAYLOAD_VARIANT_V1)
        self.executable.serialize(serializer)
        self.extra_config.serialize(serializer)


class TransactionPayloadOrderless:
    """Transaction payload wrapper for orderless transactions with replay nonce support."""

    def __init__(self, inner_payload: TransactionInnerPayloadV1) -> None:
        self.inner_payload = inner_payload

    def serialize(self, serializer: Serializer) -> None:
        serializer.uleb128(_PAYLOAD_VARIANT_ORDERLESS)
        self.inner_payload.serialize(serializer)


@dataclass
class SimpleTransaction:
    raw_transaction: RawTransaction
    fee_payer_address: AccountAddress | None = None


@dataclass
class InputEntryFunctionData:
    function: str
    function_arguments: list[Any] = field(default_factory=lambda: [])
    type_arguments: list[str] | None = None


def generate_expire_timestamp(
    time_delta_ms: int = 0,
    default_txn_expiry_sec: int = 20,
) -> int:
    return int((time.time() * 1000 + time_delta_ms) / 1000) + default_txn_expiry_sec


def build_simple_transaction_sync(
    sender: str | AccountAddress,
    data: InputEntryFunctionData,
    chain_id: int,
    gas_unit_price: int,
    abi: MoveFunction,
    with_fee_payer: bool,
    replay_protection_nonce: int,
    time_delta_ms: int = 0,
    max_gas_amount: int = 100_000,
    default_txn_expiry_sec: int = 20,
) -> SimpleTransaction:
    sender_address = AccountAddress.from_str(sender) if isinstance(sender, str) else sender

    entry_function = _build_entry_function(data, abi)

    executable = TransactionExecutableEntryFunction(entry_function)
    extra_config = TransactionExtraConfigV1(
        multisig_address=None,
        replay_protection_nonce=replay_protection_nonce,
    )
    inner_payload = TransactionInnerPayloadV1(executable, extra_config)
    payload = TransactionPayloadOrderless(inner_payload)

    expire_timestamp = generate_expire_timestamp(time_delta_ms, default_txn_expiry_sec)

    raw_txn = RawTransaction(
        sender=sender_address,
        sequence_number=DEADBEEF_SEQUENCE_NUMBER,
        payload=cast("TransactionPayload", payload),
        max_gas_amount=max_gas_amount,
        gas_unit_price=gas_unit_price,
        expiration_timestamps_secs=expire_timestamp,
        chain_id=chain_id,
    )

    fee_payer = AccountAddress.from_str("0x0") if with_fee_payer else None

    return SimpleTransaction(raw_transaction=raw_txn, fee_payer_address=fee_payer)


def _build_entry_function(
    data: InputEntryFunctionData,
    abi: MoveFunction,
) -> EntryFunction:
    parts = data.function.split("::")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid function format: {data.function}, expected 'address::module::function'"
        )

    module_address = parts[0]
    module_name = parts[1]
    function_name = parts[2]

    module_id = ModuleId(AccountAddress.from_str(module_address), module_name)

    type_tags = _parse_type_arguments(data.type_arguments or [])

    first_non_signer = _find_first_non_signer_arg(abi.params)
    entry_params = abi.params[first_non_signer:]

    encoded_args = _encode_function_arguments(data.function_arguments, entry_params)

    return EntryFunction(
        module=module_id,
        function=function_name,
        ty_args=type_tags,
        args=encoded_args,
    )


def _find_first_non_signer_arg(params: list[str]) -> int:
    for i, param in enumerate(params):
        normalized = param.replace("&", "").strip()
        if normalized != "signer":
            return i
    return len(params)


def _parse_type_arguments(type_args: list[str]) -> list[TypeTag]:
    return [_parse_type_tag(t) for t in type_args]


def _parse_type_tag(type_str: str) -> TypeTag:
    type_str = type_str.strip()

    if type_str == "bool":
        return TypeTag(TypeTag.BOOL)
    if type_str == "u8":
        return TypeTag(TypeTag.U8)
    if type_str == "u16":
        return TypeTag(TypeTag.U16)
    if type_str == "u32":
        return TypeTag(TypeTag.U32)
    if type_str == "u64":
        return TypeTag(TypeTag.U64)
    if type_str == "u128":
        return TypeTag(TypeTag.U128)
    if type_str == "u256":
        return TypeTag(TypeTag.U256)
    if type_str == "address":
        return TypeTag(TypeTag.ACCOUNT_ADDRESS)
    if type_str == "signer":
        return TypeTag(TypeTag.SIGNER)

    if type_str.startswith("vector<") and type_str.endswith(">"):
        inner_type = type_str[7:-1]
        inner_tag = _parse_type_tag(inner_type)
        return TypeTag((TypeTag.VECTOR, inner_tag))

    return TypeTag(StructTag.from_str(type_str))


def _encode_function_arguments(args: list[Any], param_types: list[str]) -> list[bytes]:
    if len(args) != len(param_types):
        raise ValueError(f"Argument count mismatch: expected {len(param_types)}, got {len(args)}")
    encoded: list[bytes] = []
    for arg, param_type in zip(args, param_types, strict=True):
        encoded.append(_encode_argument(arg, param_type))
    return encoded


def _encode_argument(arg: Any, param_type: str) -> bytes:
    serializer = Serializer()
    normalized_type = param_type.replace("&", "").strip()

    if normalized_type == "bool":
        serializer.bool(bool(arg))
    elif normalized_type == "u8":
        serializer.u8(int(arg))
    elif normalized_type == "u16":
        serializer.u16(int(arg))
    elif normalized_type == "u32":
        serializer.u32(int(arg))
    elif normalized_type == "u64":
        serializer.u64(int(arg))
    elif normalized_type == "u128":
        serializer.u128(int(arg))
    elif normalized_type == "u256":
        serializer.u256(int(arg))
    elif normalized_type == "address":
        addr = AccountAddress.from_str(arg) if isinstance(arg, str) else arg
        addr.serialize(serializer)
    elif normalized_type == "vector<u8>":
        if isinstance(arg, bytes):
            serializer.to_bytes(arg)
        elif isinstance(arg, str):
            serializer.to_bytes(bytes.fromhex(arg.removeprefix("0x")))
        else:
            serializer.to_bytes(bytes(arg))
    elif normalized_type.startswith("vector<"):
        return _encode_vector_bytes(arg, normalized_type)
    elif normalized_type == "0x1::string::String":
        serializer.str(str(arg))
    elif "::option::Option<" in normalized_type:
        return _encode_option_bytes(arg, normalized_type)
    elif "::object::Object<" in normalized_type or normalized_type.endswith("::Object"):
        addr = AccountAddress.from_str(arg) if isinstance(arg, str) else arg
        addr.serialize(serializer)
    else:
        raise ValueError(
            f"Cannot encode argument of type '{type(arg).__name__}' "
            f"for param type '{normalized_type}'"
        )

    return serializer.output()


def _encode_vector_bytes(arg: list[Any], param_type: str) -> bytes:
    inner_match = param_type[7:-1]

    serializer = Serializer()
    serializer.uleb128(len(arg))
    for item in arg:
        item_bytes = _encode_argument(item, inner_match)
        serializer.fixed_bytes(item_bytes)  # pyright: ignore[reportUnknownMemberType]
    return serializer.output()


def _encode_option_bytes(arg: Any | None, param_type: str) -> bytes:
    serializer = Serializer()
    if arg is None:
        serializer.u8(0)
    else:
        serializer.u8(1)
        inner_start = param_type.find("Option<") + 7
        inner_end = param_type.rfind(">")
        inner_type = param_type[inner_start:inner_end]
        inner_bytes = _encode_argument(arg, inner_type)
        serializer.fixed_bytes(inner_bytes)  # pyright: ignore[reportUnknownMemberType]
    return serializer.output()
