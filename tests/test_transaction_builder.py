"""Unit tests for decibel._transaction_builder module.

Covers: generate_expire_timestamp, build_simple_transaction_sync,
_build_entry_function, _find_first_non_signer_arg, _parse_type_tag,
_encode_argument, _encode_vector_bytes, _encode_option_bytes,
_encode_function_arguments, TransactionExtraConfigV1 (serialize/deserialize),
TransactionPayloadOrderless (serialize).
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.bcs import Deserializer, Serializer
from aptos_sdk.type_tag import StructTag, TypeTag

from decibel._transaction_builder import (
    DEADBEEF_SEQUENCE_NUMBER,
    InputEntryFunctionData,
    SimpleTransaction,
    TransactionExtraConfigV1,
    TransactionPayloadOrderless,
    _build_entry_function,
    _encode_argument,
    _encode_function_arguments,
    _encode_option_bytes,
    _encode_vector_bytes,
    _find_first_non_signer_arg,
    _parse_type_tag,
    build_simple_transaction_sync,
    generate_expire_timestamp,
)

# ---------------------------------------------------------------------------
# Helper – create a minimal MoveFunction mock
# ---------------------------------------------------------------------------


def _make_abi(params: list[str]) -> Any:
    """Create a minimal MoveFunction-like object with given params."""
    mock = MagicMock()
    mock.params = params
    return mock


# ---------------------------------------------------------------------------
# generate_expire_timestamp
# ---------------------------------------------------------------------------


class TestGenerateExpireTimestamp:
    def test_returns_int(self) -> None:
        result = generate_expire_timestamp()
        assert isinstance(result, int)

    def test_in_the_future(self) -> None:
        now = int(time.time())
        result = generate_expire_timestamp()
        assert result > now

    def test_approximately_now_plus_20(self) -> None:
        before = int(time.time())
        result = generate_expire_timestamp()
        after = int(time.time())
        # Should be now + 20 seconds (default expiry)
        assert before + 19 <= result <= after + 22

    def test_time_delta_ms_shifts_result(self) -> None:
        base = generate_expire_timestamp(time_delta_ms=0)
        shifted = generate_expire_timestamp(time_delta_ms=5000)
        # 5000ms = 5s shift
        assert shifted >= base + 4

    def test_negative_time_delta_ms_shifts_backward(self) -> None:
        base = generate_expire_timestamp(time_delta_ms=0)
        shifted = generate_expire_timestamp(time_delta_ms=-10000)
        assert shifted <= base - 9

    def test_custom_default_txn_expiry_sec(self) -> None:
        before = int(time.time())
        result = generate_expire_timestamp(default_txn_expiry_sec=60)
        after = int(time.time())
        assert before + 59 <= result <= after + 62


# ---------------------------------------------------------------------------
# build_simple_transaction_sync
# ---------------------------------------------------------------------------


class TestBuildSimpleTransactionSync:
    def _make_abi_for_build(self) -> Any:
        """ABI with one non-signer u64 param."""
        return _make_abi(["&signer", "u64"])

    def test_returns_simple_transaction(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=2,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=12345,
        )
        assert isinstance(result, SimpleTransaction)

    def test_fee_payer_address_set_when_with_fee_payer(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=2,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=True,
            replay_protection_nonce=99,
        )
        assert result.fee_payer_address is not None
        assert str(result.fee_payer_address) == str(AccountAddress.from_str("0x0"))

    def test_fee_payer_address_none_when_no_fee_payer(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=2,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=99,
        )
        assert result.fee_payer_address is None

    def test_uses_deadbeef_sequence_number(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=2,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=1,
        )
        assert result.raw_transaction.sequence_number == DEADBEEF_SEQUENCE_NUMBER

    def test_correct_gas_unit_price(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=2,
            gas_unit_price=777,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=1,
        )
        assert result.raw_transaction.gas_unit_price == 777

    def test_correct_max_gas_amount(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=2,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=1,
            max_gas_amount=500_000,
        )
        assert result.raw_transaction.max_gas_amount == 500_000

    def test_sender_as_string(self) -> None:
        abi = self._make_abi_for_build()
        sender_str = "0x" + "aa" * 32
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender_str,
            data=data,
            chain_id=2,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=1,
        )
        assert isinstance(result, SimpleTransaction)

    def test_correct_chain_id(self) -> None:
        abi = self._make_abi_for_build()
        sender = AccountAddress.from_str("0x" + "aa" * 32)
        data = InputEntryFunctionData(
            function=f"{'0x' + 'ab' * 32}::module::func",
            function_arguments=[42],
            type_arguments=[],
        )
        result = build_simple_transaction_sync(
            sender=sender,
            data=data,
            chain_id=42,
            gas_unit_price=100,
            abi=abi,
            with_fee_payer=False,
            replay_protection_nonce=1,
        )
        assert result.raw_transaction.chain_id == 42


# ---------------------------------------------------------------------------
# _build_entry_function
# ---------------------------------------------------------------------------


class TestBuildEntryFunction:
    def test_parses_valid_function_id(self) -> None:
        pkg = "0x" + "ab" * 32
        abi = _make_abi(["&signer", "u64"])
        data = InputEntryFunctionData(
            function=f"{pkg}::my_module::my_func",
            function_arguments=[999],
            type_arguments=[],
        )
        entry_fn = _build_entry_function(data, abi)
        assert entry_fn.function == "my_func"
        assert str(entry_fn.module.address) == pkg

    def test_invalid_function_id_raises(self) -> None:
        abi = _make_abi(["u64"])
        data = InputEntryFunctionData(
            function="invalid_format",
            function_arguments=[1],
            type_arguments=[],
        )
        with pytest.raises(ValueError, match="Invalid function format"):
            _build_entry_function(data, abi)

    def test_too_many_parts_raises(self) -> None:
        abi = _make_abi(["u64"])
        data = InputEntryFunctionData(
            function="0x1::a::b::c",
            function_arguments=[1],
            type_arguments=[],
        )
        with pytest.raises(ValueError, match="Invalid function format"):
            _build_entry_function(data, abi)

    def test_type_arguments_parsed(self) -> None:
        pkg = "0x" + "ab" * 32
        abi = _make_abi([])  # No signer, no params
        data = InputEntryFunctionData(
            function=f"{pkg}::module::func",
            function_arguments=[],
            type_arguments=["u64", "bool"],
        )
        entry_fn = _build_entry_function(data, abi)
        assert len(entry_fn.ty_args) == 2

    def test_skips_signer_params_when_encoding(self) -> None:
        pkg = "0x" + "ab" * 32
        abi = _make_abi(["&signer", "&signer", "u64"])
        data = InputEntryFunctionData(
            function=f"{pkg}::module::func",
            function_arguments=[100],  # only 1 non-signer arg
            type_arguments=[],
        )
        entry_fn = _build_entry_function(data, abi)
        assert len(entry_fn.args) == 1

    def test_none_type_arguments_defaults_to_empty(self) -> None:
        pkg = "0x" + "ab" * 32
        abi = _make_abi(["u64"])
        data = InputEntryFunctionData(
            function=f"{pkg}::module::func",
            function_arguments=[1],
            type_arguments=None,
        )
        entry_fn = _build_entry_function(data, abi)
        assert entry_fn.ty_args == []


# ---------------------------------------------------------------------------
# _find_first_non_signer_arg
# ---------------------------------------------------------------------------


class TestFindFirstNonSignerArg:
    def test_no_params(self) -> None:
        assert _find_first_non_signer_arg([]) == 0

    def test_all_signers(self) -> None:
        params = ["&signer", "signer", "&signer"]
        assert _find_first_non_signer_arg(params) == len(params)

    def test_first_non_signer_at_zero(self) -> None:
        params = ["u64", "bool"]
        assert _find_first_non_signer_arg(params) == 0

    def test_first_non_signer_after_signer(self) -> None:
        params = ["&signer", "u64", "bool"]
        assert _find_first_non_signer_arg(params) == 1

    def test_multiple_signers_then_non_signer(self) -> None:
        params = ["signer", "&signer", "address"]
        assert _find_first_non_signer_arg(params) == 2

    def test_reference_signer(self) -> None:
        params = ["& signer", "u128"]
        # "& signer" stripped becomes "signer"
        assert _find_first_non_signer_arg(params) == 1


# ---------------------------------------------------------------------------
# _parse_type_tag
# ---------------------------------------------------------------------------


class TestParseTypeTag:
    def test_bool(self) -> None:
        tag = _parse_type_tag("bool")
        assert tag.value == TypeTag.BOOL

    def test_u8(self) -> None:
        tag = _parse_type_tag("u8")
        assert tag.value == TypeTag.U8

    def test_u16(self) -> None:
        tag = _parse_type_tag("u16")
        assert tag.value == TypeTag.U16

    def test_u32(self) -> None:
        tag = _parse_type_tag("u32")
        assert tag.value == TypeTag.U32

    def test_u64(self) -> None:
        tag = _parse_type_tag("u64")
        assert tag.value == TypeTag.U64

    def test_u128(self) -> None:
        tag = _parse_type_tag("u128")
        assert tag.value == TypeTag.U128

    def test_u256(self) -> None:
        tag = _parse_type_tag("u256")
        assert tag.value == TypeTag.U256

    def test_address(self) -> None:
        tag = _parse_type_tag("address")
        assert tag.value == TypeTag.ACCOUNT_ADDRESS

    def test_signer(self) -> None:
        tag = _parse_type_tag("signer")
        assert tag.value == TypeTag.SIGNER

    def test_vector_u8(self) -> None:
        tag = _parse_type_tag("vector<u8>")
        assert isinstance(tag.value, tuple)
        assert tag.value[0] == TypeTag.VECTOR

    def test_vector_u64(self) -> None:
        tag = _parse_type_tag("vector<u64>")
        assert isinstance(tag.value, tuple)
        assert tag.value[0] == TypeTag.VECTOR

    def test_struct_type(self) -> None:
        tag = _parse_type_tag("0x1::string::String")
        assert isinstance(tag.value, StructTag)

    def test_whitespace_stripped(self) -> None:
        tag = _parse_type_tag("  u64  ")
        assert tag.value == TypeTag.U64


# ---------------------------------------------------------------------------
# _encode_argument
# ---------------------------------------------------------------------------


class TestEncodeArgument:
    def _decode_bool(self, data: bytes) -> bool:
        d = Deserializer(data)
        return d.bool()

    def _decode_u8(self, data: bytes) -> int:
        d = Deserializer(data)
        return d.u8()

    def _decode_u16(self, data: bytes) -> int:
        d = Deserializer(data)
        return d.u16()

    def _decode_u32(self, data: bytes) -> int:
        d = Deserializer(data)
        return d.u32()

    def _decode_u64(self, data: bytes) -> int:
        d = Deserializer(data)
        return d.u64()

    def _decode_u128(self, data: bytes) -> int:
        d = Deserializer(data)
        return d.u128()

    def _decode_u256(self, data: bytes) -> int:
        d = Deserializer(data)
        return d.u256()

    def test_bool_true(self) -> None:
        data = _encode_argument(True, "bool")
        assert self._decode_bool(data) is True

    def test_bool_false(self) -> None:
        data = _encode_argument(False, "bool")
        assert self._decode_bool(data) is False

    def test_u8(self) -> None:
        data = _encode_argument(255, "u8")
        assert self._decode_u8(data) == 255

    def test_u16(self) -> None:
        data = _encode_argument(65535, "u16")
        assert self._decode_u16(data) == 65535

    def test_u32(self) -> None:
        data = _encode_argument(4294967295, "u32")
        assert self._decode_u32(data) == 4294967295

    def test_u64(self) -> None:
        data = _encode_argument(1234567890, "u64")
        assert self._decode_u64(data) == 1234567890

    def test_u128(self) -> None:
        val = 2**64 + 42
        data = _encode_argument(val, "u128")
        assert self._decode_u128(data) == val

    def test_u256(self) -> None:
        val = 2**128 + 99
        data = _encode_argument(val, "u256")
        assert self._decode_u256(data) == val

    def test_address_from_string(self) -> None:
        addr_str = "0x" + "aa" * 32
        data = _encode_argument(addr_str, "address")
        d = Deserializer(data)
        decoded = AccountAddress.deserialize(d)
        assert str(decoded) == addr_str

    def test_address_from_account_address(self) -> None:
        addr = AccountAddress.from_str("0x" + "bb" * 32)
        data = _encode_argument(addr, "address")
        d = Deserializer(data)
        decoded = AccountAddress.deserialize(d)
        assert str(decoded) == str(addr)

    def test_vector_u8_from_bytes(self) -> None:
        payload = b"\x01\x02\x03"
        data = _encode_argument(payload, "vector<u8>")
        d = Deserializer(data)
        assert d.to_bytes() == payload

    def test_vector_u8_from_hex_string(self) -> None:
        data = _encode_argument("0x010203", "vector<u8>")
        d = Deserializer(data)
        assert d.to_bytes() == bytes([1, 2, 3])

    def test_vector_u8_from_hex_string_no_prefix(self) -> None:
        data = _encode_argument("010203", "vector<u8>")
        d = Deserializer(data)
        assert d.to_bytes() == bytes([1, 2, 3])

    def test_vector_u8_from_list(self) -> None:
        data = _encode_argument([10, 20, 30], "vector<u8>")
        d = Deserializer(data)
        assert d.to_bytes() == bytes([10, 20, 30])

    def test_string_encoding(self) -> None:
        data = _encode_argument("hello world", "0x1::string::String")
        d = Deserializer(data)
        assert d.str() == "hello world"

    def test_option_some_u64(self) -> None:
        data = _encode_argument(42, "0x1::option::Option<u64>")
        d = Deserializer(data)
        flag = d.u8()
        assert flag == 1  # Some
        val = d.u64()
        assert val == 42

    def test_option_none(self) -> None:
        data = _encode_argument(None, "0x1::option::Option<u64>")
        d = Deserializer(data)
        flag = d.u8()
        assert flag == 0  # None

    def test_object_type_from_string(self) -> None:
        addr_str = "0x" + "cc" * 32
        data = _encode_argument(addr_str, "0x1::object::Object<0x1::coin::Coin>")
        d = Deserializer(data)
        decoded = AccountAddress.deserialize(d)
        assert str(decoded) == addr_str

    def test_object_type_suffix(self) -> None:
        addr_str = "0x" + "dd" * 32
        data = _encode_argument(addr_str, "some::module::Object")
        d = Deserializer(data)
        decoded = AccountAddress.deserialize(d)
        assert str(decoded) == addr_str

    def test_reference_param_type_stripped(self) -> None:
        # "&u64" should be treated same as "u64"
        data = _encode_argument(99, "&u64")
        d = Deserializer(data)
        assert d.u64() == 99

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot encode argument"):
            _encode_argument("something", "totally::unknown::Type")

    def test_non_u8_vector_via_encode_argument(self) -> None:
        """_encode_argument dispatches to _encode_vector_bytes for non-u8 vectors."""
        data = _encode_argument([10, 20], "vector<u64>")
        d = Deserializer(data)
        length = d.uleb128()
        assert length == 2


# ---------------------------------------------------------------------------
# _encode_vector_bytes
# ---------------------------------------------------------------------------


class TestEncodeVectorBytes:
    def test_vector_of_u64(self) -> None:
        data = _encode_vector_bytes([1, 2, 3], "vector<u64>")
        d = Deserializer(data)
        length = d.uleb128()
        assert length == 3
        # Each u64 is 8 bytes (fixed)
        # The deserializer for fixed_bytes needs to know the size
        # Just check the length prefix is correct
        assert len(data) > 0

    def test_vector_of_u8(self) -> None:
        data = _encode_vector_bytes([10, 20, 30], "vector<u8>")
        assert len(data) > 0

    def test_empty_vector(self) -> None:
        data = _encode_vector_bytes([], "vector<u64>")
        d = Deserializer(data)
        length = d.uleb128()
        assert length == 0

    def test_vector_of_bool(self) -> None:
        data = _encode_vector_bytes([True, False, True], "vector<bool>")
        d = Deserializer(data)
        length = d.uleb128()
        assert length == 3


# ---------------------------------------------------------------------------
# _encode_option_bytes
# ---------------------------------------------------------------------------


class TestEncodeOptionBytes:
    def test_none_produces_zero_byte(self) -> None:
        data = _encode_option_bytes(None, "0x1::option::Option<u64>")
        d = Deserializer(data)
        assert d.u8() == 0

    def test_some_u64_produces_one_then_value(self) -> None:
        data = _encode_option_bytes(42, "0x1::option::Option<u64>")
        d = Deserializer(data)
        assert d.u8() == 1
        assert d.u64() == 42

    def test_some_bool(self) -> None:
        data = _encode_option_bytes(True, "0x1::option::Option<bool>")
        d = Deserializer(data)
        assert d.u8() == 1
        assert d.bool() is True

    def test_some_u128(self) -> None:
        val = 2**64 + 1
        data = _encode_option_bytes(val, "0x1::option::Option<u128>")
        d = Deserializer(data)
        assert d.u8() == 1
        assert d.u128() == val


# ---------------------------------------------------------------------------
# _encode_function_arguments
# ---------------------------------------------------------------------------


class TestEncodeFunctionArguments:
    def test_count_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="Argument count mismatch"):
            _encode_function_arguments([1, 2, 3], ["u64", "bool"])

    def test_empty_args_empty_params(self) -> None:
        result = _encode_function_arguments([], [])
        assert result == []

    def test_single_arg(self) -> None:
        result = _encode_function_arguments([100], ["u64"])
        assert len(result) == 1
        d = Deserializer(result[0])
        assert d.u64() == 100

    def test_multiple_args(self) -> None:
        result = _encode_function_arguments([True, 255], ["bool", "u8"])
        assert len(result) == 2
        d0 = Deserializer(result[0])
        assert d0.bool() is True
        d1 = Deserializer(result[1])
        assert d1.u8() == 255


# ---------------------------------------------------------------------------
# TransactionExtraConfigV1 serialize / deserialize
# ---------------------------------------------------------------------------


class TestTransactionExtraConfigV1:
    def _roundtrip(
        self,
        multisig: AccountAddress | None = None,
        nonce: int | None = None,
    ) -> TransactionExtraConfigV1:
        config = TransactionExtraConfigV1(
            multisig_address=multisig,
            replay_protection_nonce=nonce,
        )
        serializer = Serializer()
        config.serialize(serializer)
        deserializer = Deserializer(serializer.output())
        return TransactionExtraConfigV1.deserialize(deserializer)

    def test_no_multisig_no_nonce(self) -> None:
        result = self._roundtrip()
        assert result.multisig_address is None
        assert result.replay_protection_nonce is None

    def test_with_nonce_only(self) -> None:
        result = self._roundtrip(nonce=98765)
        assert result.multisig_address is None
        assert result.replay_protection_nonce == 98765

    def test_with_multisig_only(self) -> None:
        addr = AccountAddress.from_str("0x" + "ee" * 32)
        result = self._roundtrip(multisig=addr)
        assert result.multisig_address is not None
        assert str(result.multisig_address) == str(addr)
        assert result.replay_protection_nonce is None

    def test_with_both(self) -> None:
        addr = AccountAddress.from_str("0x" + "ff" * 32)
        result = self._roundtrip(multisig=addr, nonce=55555)
        assert str(result.multisig_address) == str(addr)  # type: ignore[arg-type]
        assert result.replay_protection_nonce == 55555

    def test_invalid_variant_raises(self) -> None:
        serializer = Serializer()
        serializer.uleb128(99)  # Wrong variant
        deserializer = Deserializer(serializer.output())
        with pytest.raises(ValueError, match="Unknown TransactionExtraConfig variant"):
            TransactionExtraConfigV1.deserialize(deserializer)

    def test_serialize_writes_variant_zero(self) -> None:
        config = TransactionExtraConfigV1()
        serializer = Serializer()
        config.serialize(serializer)
        data = serializer.output()
        # First byte should be variant 0 (uleb128 of 0 = 0x00)
        assert data[0] == 0


# ---------------------------------------------------------------------------
# TransactionPayloadOrderless serialize
# ---------------------------------------------------------------------------


class TestTransactionPayloadOrderless:
    def test_serialize_starts_with_variant_4(self) -> None:
        from aptos_sdk.transactions import EntryFunction, ModuleId

        from decibel._transaction_builder import (
            TransactionExecutableEntryFunction,
            TransactionInnerPayloadV1,
        )

        # Create a real EntryFunction
        module_id = ModuleId(AccountAddress.from_str("0x1"), "m")
        entry_fn = EntryFunction(module=module_id, function="f", ty_args=[], args=[])
        executable = TransactionExecutableEntryFunction(entry_fn)

        extra_config = TransactionExtraConfigV1(replay_protection_nonce=1)
        inner = TransactionInnerPayloadV1(executable, extra_config)
        payload = TransactionPayloadOrderless(inner)

        serializer = Serializer()
        payload.serialize(serializer)
        data = serializer.output()

        # First uleb128 byte = variant 4 = 0x04
        assert data[0] == 4

    def test_serialize_is_non_empty(self) -> None:
        from aptos_sdk.transactions import EntryFunction, ModuleId

        from decibel._transaction_builder import (
            TransactionExecutableEntryFunction,
            TransactionInnerPayloadV1,
        )

        module_id = ModuleId(AccountAddress.from_str("0x1"), "m")
        entry_fn = EntryFunction(module=module_id, function="f", ty_args=[], args=[])
        executable = TransactionExecutableEntryFunction(entry_fn)
        extra_config = TransactionExtraConfigV1()
        inner = TransactionInnerPayloadV1(executable, extra_config)
        payload = TransactionPayloadOrderless(inner)

        serializer = Serializer()
        payload.serialize(serializer)
        assert len(serializer.output()) > 0


# ---------------------------------------------------------------------------
# InputEntryFunctionData dataclass
# ---------------------------------------------------------------------------


class TestInputEntryFunctionData:
    def test_default_function_arguments(self) -> None:
        data = InputEntryFunctionData(function="0x1::m::f")
        assert data.function_arguments == []

    def test_default_type_arguments(self) -> None:
        data = InputEntryFunctionData(function="0x1::m::f")
        assert data.type_arguments is None

    def test_custom_values(self) -> None:
        data = InputEntryFunctionData(
            function="0x1::m::f",
            function_arguments=[1, 2, 3],
            type_arguments=["u64"],
        )
        assert data.function_arguments == [1, 2, 3]
        assert data.type_arguments == ["u64"]


# ---------------------------------------------------------------------------
# SimpleTransaction dataclass
# ---------------------------------------------------------------------------


class TestSimpleTransaction:
    def test_default_fee_payer_address(self) -> None:
        mock_raw = MagicMock()
        txn = SimpleTransaction(raw_transaction=mock_raw)
        assert txn.fee_payer_address is None

    def test_with_fee_payer_address(self) -> None:
        mock_raw = MagicMock()
        addr = AccountAddress.from_str("0x" + "aa" * 32)
        txn = SimpleTransaction(raw_transaction=mock_raw, fee_payer_address=addr)
        assert txn.fee_payer_address is addr
