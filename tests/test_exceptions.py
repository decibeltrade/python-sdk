"""Tests for decibel._exceptions module."""

from __future__ import annotations

import pytest

from decibel._exceptions import TxnConfirmError, TxnSubmitError


class TestTxnConfirmError:
    def test_init_stores_tx_hash(self) -> None:
        err = TxnConfirmError("0xdeadbeef", "timed out")
        assert err.tx_hash == "0xdeadbeef"

    def test_init_formats_message_with_tx_hash(self) -> None:
        err = TxnConfirmError("0xabc123", "transaction reverted")
        assert "0xabc123" in str(err)
        assert "transaction reverted" in str(err)

    def test_is_exception(self) -> None:
        err = TxnConfirmError("0x1", "some error")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(TxnConfirmError) as exc_info:
            raise TxnConfirmError("0xhash", "confirmation failed")
        assert exc_info.value.tx_hash == "0xhash"

    def test_message_format_contains_transaction_prefix(self) -> None:
        err = TxnConfirmError("0xfeed", "dropped")
        assert str(err) == "Transaction 0xfeed: dropped"

    def test_empty_message(self) -> None:
        err = TxnConfirmError("0x0", "")
        assert err.tx_hash == "0x0"
        assert "0x0" in str(err)

    def test_long_tx_hash(self) -> None:
        long_hash = "0x" + "a" * 64
        err = TxnConfirmError(long_hash, "msg")
        assert err.tx_hash == long_hash
        assert long_hash in str(err)


class TestTxnSubmitError:
    def test_init_stores_original_exception(self) -> None:
        original = ValueError("connection refused")
        err = TxnSubmitError("submit failed", original_exception=original)
        assert err.original_exception is original

    def test_init_with_no_original_exception(self) -> None:
        err = TxnSubmitError("failed without cause")
        assert err.original_exception is None

    def test_message_is_set(self) -> None:
        err = TxnSubmitError("network timeout")
        assert str(err) == "network timeout"

    def test_is_exception(self) -> None:
        err = TxnSubmitError("some error")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        original = ConnectionError("host unreachable")
        with pytest.raises(TxnSubmitError) as exc_info:
            raise TxnSubmitError("submit failed", original_exception=original)
        assert exc_info.value.original_exception is original

    def test_original_exception_defaults_to_none(self) -> None:
        err = TxnSubmitError("error message")
        assert err.original_exception is None

    def test_with_various_original_exception_types(self) -> None:
        for exc_type in [ValueError, RuntimeError, TimeoutError, OSError]:
            original = exc_type("inner error")
            err = TxnSubmitError("outer message", original_exception=original)
            assert isinstance(err.original_exception, exc_type)
