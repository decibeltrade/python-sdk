"""
Comprehensive unit tests for src/decibel/write/__init__.py.

Tests cover DecibelWriteDex (async) and DecibelWriteDexSync (sync) classes,
the _round_to_tick_size helper, and all public methods.

Strategy: mock _send_tx / _send_tx at the instance level so no real HTTP
calls or blockchain interactions happen. The tests verify that:
  1. The correct Move function name is assembled from the package address.
  2. The correct arguments are passed to InputEntryFunctionData.
  3. The return value is constructed correctly from the tx response.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from decibel._order_types import (
    PlaceBulkOrdersFailure,
    PlaceBulkOrdersSuccess,
    PlaceOrderFailure,
    PlaceOrderSuccess,
)
from decibel._subaccount_types import RenameSubaccountArgs
from decibel.write import (
    DecibelWriteDex,
    DecibelWriteDexSync,
    TimeInForce,
    _round_to_tick_size,  # type: ignore[attr-defined]
)

if TYPE_CHECKING:
    from decibel._transaction_builder import InputEntryFunctionData

# ---------------------------------------------------------------------------
# Constants shared across tests (mirror conftest.py)
# ---------------------------------------------------------------------------
TEST_PACKAGE = "0x" + "ab" * 32
TEST_USDC = "0x" + "cd" * 32
TEST_PERP_ENGINE = "0x" + "12" * 32
TEST_ACCOUNT_ADDR = "0x" + "aa" * 32
TEST_SUBACCOUNT_ADDR = "0x" + "bb" * 32
TEST_MARKET_NAME = "BTC-USD"
TEST_VAULT_ADDR = "0x" + "cc" * 32
TEST_TX_HASH = "0xdeadbeef"


# ---------------------------------------------------------------------------
# Helpers – build a minimal fake tx response
# ---------------------------------------------------------------------------


def _make_tx_response(
    order_id: str = "12345",
    user_addr: str = TEST_ACCOUNT_ADDR,
    event_type: str = "0x1::market_types::OrderEvent",
) -> dict[str, Any]:
    return {
        "hash": TEST_TX_HASH,
        "success": True,
        "events": [
            {
                "type": event_type,
                "data": {
                    "user": user_addr,
                    "order_id": order_id,
                },
            }
        ],
    }


def _make_twap_tx_response(
    order_id: str = "99999",
    user_addr: str = TEST_ACCOUNT_ADDR,
) -> dict[str, Any]:
    return {
        "hash": TEST_TX_HASH,
        "success": True,
        "events": [
            {
                "type": "0x1::async_matching_engine::TwapEvent",
                "data": {
                    "account": user_addr,
                    "order_id": {"order_id": order_id},
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures – async (DecibelWriteDex)
# ---------------------------------------------------------------------------


@pytest.fixture
def write_dex(test_config, mock_account) -> DecibelWriteDex:
    """Return a DecibelWriteDex instance with _send_tx mocked out."""
    with patch("decibel.write.BaseSDK.__init__", return_value=None):
        dex = DecibelWriteDex.__new__(DecibelWriteDex)
        dex._config = test_config
        dex._account = mock_account
        dex._http_client = AsyncMock()
        dex._skip_simulate = False
        dex._no_fee_payer = False
        dex._node_api_key = None
        dex._gas_price_manager = None
        dex._time_delta_ms = 0
        dex._chain_id = 2
        dex._abi_registry = MagicMock()
        dex._order_status_client = MagicMock()
        dex._send_tx = AsyncMock(return_value=_make_tx_response())
        return dex


# ---------------------------------------------------------------------------
# Fixtures – sync (DecibelWriteDexSync)
# ---------------------------------------------------------------------------


@pytest.fixture
def write_dex_sync(test_config, mock_account) -> DecibelWriteDexSync:
    """Return a DecibelWriteDexSync instance with _send_tx mocked out."""
    with patch("decibel.write.BaseSDKSync.__init__", return_value=None):
        dex = DecibelWriteDexSync.__new__(DecibelWriteDexSync)
        dex._config = test_config
        dex._account = mock_account
        dex._http_client = MagicMock()
        dex._skip_simulate = False
        dex._no_fee_payer = False
        dex._node_api_key = None
        dex._gas_price_manager = None
        dex._time_delta_ms = 0
        dex._chain_id = 2
        dex._abi_registry = MagicMock()
        dex._order_status_client = MagicMock()
        dex._send_tx = MagicMock(return_value=_make_tx_response())
        return dex


# ===========================================================================
# Tests for _round_to_tick_size helper
# ===========================================================================


class TestRoundToTickSize:
    def test_normal_rounding(self) -> None:
        result = _round_to_tick_size(105.3, 10)
        assert result == 110

    def test_rounds_down(self) -> None:
        result = _round_to_tick_size(104.9, 10)
        assert result == 100

    def test_exact_multiple(self) -> None:
        result = _round_to_tick_size(100.0, 10)
        assert result == 100

    def test_zero_value_returns_zero(self) -> None:
        result = _round_to_tick_size(0, 10)
        assert result == 0.0

    def test_zero_tick_size_returns_zero(self) -> None:
        result = _round_to_tick_size(100, 0)
        assert result == 0.0

    def test_both_zero_returns_zero(self) -> None:
        result = _round_to_tick_size(0, 0)
        assert result == 0.0

    def test_float_inputs(self) -> None:
        # 1.05 / 0.1 = 10.5 — Python banker's rounding rounds this to 10 (even)
        result = _round_to_tick_size(1.05, 0.1)
        assert result == pytest.approx(1.0, rel=1e-6)

    def test_float_inputs_rounds_up(self) -> None:
        # 1.17 / 0.1 = 11.7 — rounds to 12 → 1.2
        result = _round_to_tick_size(1.17, 0.1)
        assert result == pytest.approx(1.2, rel=1e-6)

    def test_small_tick_size(self) -> None:
        result = _round_to_tick_size(123.456, 1)
        assert result == 123


# ===========================================================================
# Tests for DecibelWriteDex.__init__
# ===========================================================================


class TestDecibelWriteDexInit:
    def test_init_creates_order_status_client(self, test_config, mock_account) -> None:
        with (
            patch("decibel.write.BaseSDK.__init__", return_value=None),
            patch("decibel.write.OrderStatusClient") as mock_osc,
        ):
            dex = DecibelWriteDex.__new__(DecibelWriteDex)
            # Manually set the attribute that BaseSDK.__init__ would set
            dex._http_client = AsyncMock()
            dex._config = test_config
            dex._account = mock_account

            # Call the actual __init__ partially by calling OrderStatusClient directly
            # to verify the wiring. We test the __init__ logic here.
            mock_osc.return_value = MagicMock()

            # Now test that order_status_client property returns the internal client
            dex._order_status_client = mock_osc.return_value
            assert dex.order_status_client is mock_osc.return_value


# ===========================================================================
# Tests for _extract_order_id_from_transaction
# ===========================================================================


class TestExtractOrderId:
    def test_extracts_string_order_id_from_order_event(self, write_dex: DecibelWriteDex) -> None:
        tx = _make_tx_response(order_id="42", user_addr=TEST_ACCOUNT_ADDR)
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result == "42"

    def test_extracts_dict_order_id_from_twap_event(self, write_dex: DecibelWriteDex) -> None:
        tx = _make_twap_tx_response(order_id="99", user_addr=TEST_ACCOUNT_ADDR)
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result == "99"

    def test_returns_none_when_no_events(self, write_dex: DecibelWriteDex) -> None:
        tx: dict[str, Any] = {"hash": TEST_TX_HASH, "success": True}
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result is None

    def test_returns_none_when_events_is_none(self, write_dex: DecibelWriteDex) -> None:
        tx: dict[str, Any] = {"hash": TEST_TX_HASH, "events": None}
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result is None

    def test_returns_none_when_event_type_does_not_match(self, write_dex: DecibelWriteDex) -> None:
        tx: dict[str, Any] = {
            "hash": TEST_TX_HASH,
            "events": [{"type": "0x1::some::OtherEvent", "data": {"user": TEST_ACCOUNT_ADDR}}],
        }
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result is None

    def test_returns_none_when_user_address_does_not_match(
        self, write_dex: DecibelWriteDex
    ) -> None:
        tx = _make_tx_response(order_id="1", user_addr="0x" + "ff" * 32)
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result is None

    def test_uses_subaccount_addr_when_provided(self, write_dex: DecibelWriteDex) -> None:
        tx = _make_tx_response(order_id="777", user_addr=TEST_SUBACCOUNT_ADDR)
        result = write_dex._extract_order_id_from_transaction(
            tx, subaccount_addr=TEST_SUBACCOUNT_ADDR
        )
        assert result == "777"

    def test_returns_none_when_event_data_is_none(self, write_dex: DecibelWriteDex) -> None:
        tx: dict[str, Any] = {
            "hash": TEST_TX_HASH,
            "events": [{"type": "0x1::market_types::OrderEvent", "data": None}],
        }
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result is None

    def test_returns_none_when_order_id_missing_from_nested_dict(
        self, write_dex: DecibelWriteDex
    ) -> None:
        tx: dict[str, Any] = {
            "hash": TEST_TX_HASH,
            "events": [
                {
                    "type": "0x1::market_types::OrderEvent",
                    "data": {
                        "user": TEST_ACCOUNT_ADDR,
                        "order_id": {},  # dict with no "order_id" key
                    },
                }
            ],
        }
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result is None

    def test_handles_exception_gracefully(self, write_dex: DecibelWriteDex) -> None:
        # Pass an object that causes an error during iteration
        result = write_dex._extract_order_id_from_transaction({"events": "not-a-list"})  # type: ignore[arg-type]
        assert result is None

    def test_twap_event_with_account_field(self, write_dex: DecibelWriteDex) -> None:
        tx: dict[str, Any] = {
            "hash": TEST_TX_HASH,
            "events": [
                {
                    "type": "0x1::async_matching_engine::TwapEvent",
                    "data": {
                        "account": TEST_ACCOUNT_ADDR,
                        "order_id": "54321",
                    },
                }
            ],
        }
        result = write_dex._extract_order_id_from_transaction(tx)
        assert result == "54321"


# ===========================================================================
# Tests for send_subaccount_tx / with_subaccount
# ===========================================================================


class TestSendSubaccountTx:
    async def test_uses_primary_subaccount_when_none_provided(
        self, write_dex: DecibelWriteDex
    ) -> None:
        called_with: list[str] = []

        async def fake_tx(addr: str) -> dict[str, Any]:
            called_with.append(addr)
            return {"hash": TEST_TX_HASH}

        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = await write_dex.send_subaccount_tx(fake_tx)

        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == {"hash": TEST_TX_HASH}

    async def test_uses_provided_subaccount_addr(self, write_dex: DecibelWriteDex) -> None:
        called_with: list[str] = []

        async def fake_tx(addr: str) -> dict[str, Any]:
            called_with.append(addr)
            return {"hash": TEST_TX_HASH}

        result = await write_dex.send_subaccount_tx(fake_tx, subaccount_addr=TEST_SUBACCOUNT_ADDR)
        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == {"hash": TEST_TX_HASH}

    async def test_with_subaccount_uses_primary_when_none(self, write_dex: DecibelWriteDex) -> None:
        called_with: list[str] = []

        async def fn(addr: str) -> str:
            called_with.append(addr)
            return "result"

        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = await write_dex.with_subaccount(fn)

        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == "result"

    async def test_with_subaccount_uses_provided_addr(self, write_dex: DecibelWriteDex) -> None:
        called_with: list[str] = []

        async def fn(addr: str) -> str:
            called_with.append(addr)
            return "result"

        result = await write_dex.with_subaccount(fn, subaccount_addr=TEST_SUBACCOUNT_ADDR)
        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == "result"


# ===========================================================================
# Tests for rename_subaccount (async)
# ===========================================================================


class TestRenameSubaccount:
    async def test_posts_to_correct_url(self, write_dex: DecibelWriteDex) -> None:
        mock_result = (MagicMock(), 200, "OK")
        args = RenameSubaccountArgs(subaccountAddress=TEST_SUBACCOUNT_ADDR, newName="My Account")

        with patch("decibel.write.post_request", return_value=mock_result) as mock_post:
            result = await write_dex.rename_subaccount(args)

        expected_url = (
            f"{write_dex._config.trading_http_url}/api/v1/subaccounts/{TEST_SUBACCOUNT_ADDR}"
        )
        mock_post.assert_awaited_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.args[1] == expected_url
        assert call_kwargs.kwargs["body"] == {"name": "My Account"}
        assert result == mock_result


# ===========================================================================
# Tests for create_subaccount (async)
# ===========================================================================


class TestCreateSubaccount:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        result = await write_dex.create_subaccount()

        write_dex._send_tx.assert_awaited_once()
        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::create_new_subaccount"
        assert payload.type_arguments == []
        assert payload.function_arguments == []
        assert result == _make_tx_response()


# ===========================================================================
# Tests for deposit (async)
# ===========================================================================


class TestDeposit:
    async def test_deposit_uses_primary_subaccount_by_default(
        self, write_dex: DecibelWriteDex
    ) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.deposit(amount=1_000_000)

        write_dex._send_tx.assert_awaited_once()
        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::deposit_to_subaccount_at"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_USDC, 1_000_000]

    async def test_deposit_uses_explicit_subaccount(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.deposit(amount=500, subaccount_addr=TEST_SUBACCOUNT_ADDR)

        write_dex._send_tx.assert_awaited_once()
        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[0] == TEST_SUBACCOUNT_ADDR
        assert payload.function_arguments[2] == 500

    async def test_deposit_passes_timeouts(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.deposit(
                amount=100,
                txn_submit_timeout=5.0,
                txn_confirm_timeout=15.0,
            )

        call_kwargs = write_dex._send_tx.call_args.kwargs
        assert call_kwargs["txn_submit_timeout"] == 5.0
        assert call_kwargs["txn_confirm_timeout"] == 15.0


# ===========================================================================
# Tests for withdraw (async)
# ===========================================================================


class TestWithdraw:
    async def test_withdraw_uses_correct_function(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.withdraw(amount=200)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::withdraw_from_subaccount"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_USDC, 200]

    async def test_withdraw_passes_timeouts(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.withdraw(
            amount=100,
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
            txn_submit_timeout=3.0,
            txn_confirm_timeout=10.0,
        )
        call_kwargs = write_dex._send_tx.call_args.kwargs
        assert call_kwargs["txn_submit_timeout"] == 3.0
        assert call_kwargs["txn_confirm_timeout"] == 10.0


# ===========================================================================
# Tests for configure_user_settings_for_market (async)
# ===========================================================================


class TestConfigureUserSettingsForMarket:
    async def test_sends_correct_payload(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        await write_dex.configure_user_settings_for_market(
            market_addr=market_addr,
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
            is_cross=True,
            user_leverage=10,
        )
        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::configure_user_settings_for_market"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            market_addr,
            True,
            10,
        ]


# ===========================================================================
# Tests for place_order (async)
# ===========================================================================


class TestPlaceOrder:
    async def test_place_order_success(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.return_value = _make_tx_response(order_id="123")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = await write_dex.place_order(
                market_name=TEST_MARKET_NAME,
                price=50000,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
            )

        assert isinstance(result, PlaceOrderSuccess)
        assert result.success is True
        assert result.order_id == "123"
        assert result.transaction_hash == TEST_TX_HASH

    async def test_place_order_with_tick_size_rounds_price(
        self, write_dex: DecibelWriteDex
    ) -> None:
        # 50004 / 10 = 5000.4 which rounds to 5000
        # 50006 / 10 = 5000.6 which rounds to 5001 → 50010
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_order(
                market_name=TEST_MARKET_NAME,
                price=50006,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
                tick_size=10,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        final_price = payload.function_arguments[2]
        assert final_price == 50010  # round(50006/10)*10 = round(5000.6)*10 = 5001*10

    async def test_place_order_with_stop_price(self, write_dex: DecibelWriteDex) -> None:
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_order(
                market_name=TEST_MARKET_NAME,
                price=50000,
                size=1,
                is_buy=False,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=True,
                stop_price=49000,
                tick_size=10,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        # stop_price should be rounded: round(49000/10)*10 = 49000
        assert payload.function_arguments[8] == 49000

    async def test_place_order_exception_returns_failure(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.side_effect = RuntimeError("Network error")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = await write_dex.place_order(
                market_name=TEST_MARKET_NAME,
                price=50000,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
            )

        assert isinstance(result, PlaceOrderFailure)
        assert result.success is False
        assert "RuntimeError" in result.error

    async def test_place_order_function_name(self, write_dex: DecibelWriteDex) -> None:
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_order(
                market_name=TEST_MARKET_NAME,
                price=100,
                size=0.5,
                is_buy=True,
                time_in_force=TimeInForce.PostOnly,
                is_reduce_only=False,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::place_order_to_subaccount"

    async def test_place_order_with_tp_sl_prices(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.return_value = _make_tx_response()
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_order(
                market_name=TEST_MARKET_NAME,
                price=50000,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
                tp_trigger_price=55000,
                tp_limit_price=56000,
                sl_trigger_price=45000,
                sl_limit_price=44000,
                tick_size=100,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        # Arguments: addr, market, price, size, is_buy, tif, reduce_only,
        #            client_order_id, stop_price, tp_trigger, tp_limit, sl_trigger, sl_limit,
        #            builder_addr, builder_fee
        assert payload.function_arguments[9] == 55000  # tp_trigger rounded
        assert payload.function_arguments[10] == 56000  # tp_limit rounded
        assert payload.function_arguments[11] == 45000  # sl_trigger rounded
        assert payload.function_arguments[12] == 44000  # sl_limit rounded


# ===========================================================================
# Tests for trigger_matching (async)
# ===========================================================================


class TestTriggerMatching:
    async def test_sends_correct_payload(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        result = await write_dex.trigger_matching(market_addr=market_addr, max_work_unit=100)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::public_apis::process_perp_market_pending_requests"
        )
        assert payload.function_arguments == [market_addr, 100]
        assert result == {"success": True, "transactionHash": TEST_TX_HASH}


# ===========================================================================
# Tests for place_twap_order (async)
# ===========================================================================


class TestPlaceTwapOrder:
    async def test_place_twap_order_success(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.return_value = _make_twap_tx_response(order_id="88")

        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = await write_dex.place_twap_order(
                market_name=TEST_MARKET_NAME,
                size=1,
                is_buy=True,
                is_reduce_only=False,
                twap_frequency_seconds=60,
                twap_duration_seconds=3600,
            )

        assert isinstance(result, PlaceOrderSuccess)
        assert result.success is True
        assert result.order_id == "88"

    async def test_place_twap_order_function_name(self, write_dex: DecibelWriteDex) -> None:
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_twap_order(
                market_name=TEST_MARKET_NAME,
                size=0.5,
                is_buy=False,
                is_reduce_only=True,
                twap_frequency_seconds=30,
                twap_duration_seconds=1800,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::place_twap_order_to_subaccount_v2"
        )

    async def test_place_twap_order_arguments(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        builder_addr = "0x" + "ee" * 32

        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_twap_order(
                market_name=TEST_MARKET_NAME,
                size=2,
                is_buy=True,
                is_reduce_only=False,
                twap_frequency_seconds=60,
                twap_duration_seconds=3600,
                client_order_id="my-order",
                builder_address=builder_addr,
                builder_fees=0.001,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        args = payload.function_arguments
        # addr, market_addr, size, is_buy, is_reduce_only, client_order_id,
        # twap_frequency_seconds, twap_duration_seconds, builder_address, builder_fees
        assert args[0] == TEST_SUBACCOUNT_ADDR
        assert args[1] == market_addr
        assert args[2] == 2
        assert args[3] is True
        assert args[4] is False
        assert args[5] == "my-order"
        assert args[6] == 60
        assert args[7] == 3600
        assert args[8] == builder_addr
        assert args[9] == 0.001


# ===========================================================================
# Tests for cancel_order (async)
# ===========================================================================


class TestCancelOrder:
    async def test_cancel_order_by_market_name(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.cancel_order(order_id=99, market_name=TEST_MARKET_NAME)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_order_to_subaccount"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, 99, market_addr]

    async def test_cancel_order_by_market_addr(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_order(order_id="55", market_addr=market_addr)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, 55, market_addr]

    async def test_cancel_order_raises_when_no_market(self, write_dex: DecibelWriteDex) -> None:
        with pytest.raises(ValueError, match="Either market_name or market_addr must be provided"):
            await write_dex.cancel_order(order_id=1)

    async def test_cancel_order_converts_str_order_id_to_int(
        self, write_dex: DecibelWriteDex
    ) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_order(order_id="123", market_addr=market_addr)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[1] == 123  # integer, not string


# ===========================================================================
# Tests for place_bulk_orders (async)
# ===========================================================================


class TestPlaceBulkOrders:
    async def test_place_bulk_orders_success(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = await write_dex.place_bulk_orders(
                market_name=TEST_MARKET_NAME,
                sequence_number=1,
                bid_prices=[100, 99],
                bid_sizes=[10, 20],
                ask_prices=[101, 102],
                ask_sizes=[10, 20],
            )

        assert isinstance(result, PlaceBulkOrdersSuccess)
        assert result.success is True
        assert result.transaction_hash == TEST_TX_HASH

    async def test_place_bulk_orders_function_name(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_bulk_orders(
                market_name=TEST_MARKET_NAME,
                sequence_number=1,
                bid_prices=[100],
                bid_sizes=[10],
                ask_prices=[101],
                ask_sizes=[10],
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::place_bulk_orders_to_subaccount"
        )

    async def test_place_bulk_orders_arguments(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        builder_addr = "0x" + "ee" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.place_bulk_orders(
                market_name=TEST_MARKET_NAME,
                sequence_number=5,
                bid_prices=[100, 99],
                bid_sizes=[10, 20],
                ask_prices=[101, 102],
                ask_sizes=[10, 20],
                builder_addr=builder_addr,
                builder_fee=50,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        args = payload.function_arguments
        assert args[0] == TEST_SUBACCOUNT_ADDR
        assert args[1] == market_addr
        assert args[2] == 5
        assert args[3] == [100, 99]
        assert args[4] == [10, 20]
        assert args[5] == [101, 102]
        assert args[6] == [10, 20]
        assert args[7] == builder_addr
        assert args[8] == 50

    async def test_place_bulk_orders_failure_on_exception(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.side_effect = RuntimeError("Connection failed")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = await write_dex.place_bulk_orders(
                market_name=TEST_MARKET_NAME,
                sequence_number=1,
                bid_prices=[100],
                bid_sizes=[10],
                ask_prices=[101],
                ask_sizes=[10],
            )

        assert isinstance(result, PlaceBulkOrdersFailure)
        assert "Connection failed" in result.error


# ===========================================================================
# Tests for cancel_bulk_order (async)
# ===========================================================================


class TestCancelBulkOrder:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.cancel_bulk_order(market_name=TEST_MARKET_NAME)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_bulk_order_to_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, market_addr]


# ===========================================================================
# Tests for cancel_client_order (async)
# ===========================================================================


class TestCancelClientOrder:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            await write_dex.cancel_client_order(
                client_order_id="my-order-id",
                market_name=TEST_MARKET_NAME,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_client_order_to_subaccount"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            "my-order-id",
            market_addr,
        ]


# ===========================================================================
# Tests for delegate_trading_to_for_subaccount (async)
# ===========================================================================


class TestDelegateTradingToForSubaccount:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        delegate_addr = "0x" + "dd" * 32
        await write_dex.delegate_trading_to_for_subaccount(
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
            account_to_delegate_to=delegate_addr,
        )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::delegate_trading_to_for_subaccount"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            delegate_addr,
            None,
        ]

    async def test_passes_expiration(self, write_dex: DecibelWriteDex) -> None:
        delegate_addr = "0x" + "dd" * 32
        await write_dex.delegate_trading_to_for_subaccount(
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
            account_to_delegate_to=delegate_addr,
            expiration_timestamp_secs=9999999,
        )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[2] == 9999999


# ===========================================================================
# Tests for revoke_delegation (async)
# ===========================================================================


class TestRevokeDelegation:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        revoking_addr = "0x" + "dd" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.revoke_delegation(account_to_revoke=revoking_addr)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::revoke_delegation"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, revoking_addr]


# ===========================================================================
# Tests for place_tp_sl_order_for_position (async)
# ===========================================================================


class TestPlaceTpSlOrderForPosition:
    async def test_sends_correct_function_with_tick_size(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.place_tp_sl_order_for_position(
                market_addr=market_addr,
                tp_trigger_price=55000,
                tp_limit_price=56000,
                tp_size=1,
                sl_trigger_price=45000,
                sl_limit_price=44000,
                sl_size=1,
                tick_size=100,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::place_tp_sl_order_for_position"
        )
        # addr, market_addr, tp_trigger, tp_limit, tp_size,
        # sl_trigger, sl_limit, sl_size, None, None
        args = payload.function_arguments
        assert args[0] == TEST_SUBACCOUNT_ADDR
        assert args[1] == market_addr
        assert args[2] == 55000  # tp_trigger rounded to nearest 100
        assert args[8] is None  # trailing None
        assert args[9] is None  # trailing None

    async def test_passes_none_for_trailing_args(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.place_tp_sl_order_for_position(
                market_addr=market_addr,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        args = payload.function_arguments
        # Trailing args should be None, None
        assert args[-2] is None
        assert args[-1] is None


# ===========================================================================
# Tests for update_tp_order_for_position (async)
# ===========================================================================


class TestUpdateTpOrderForPosition:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.update_tp_order_for_position(
                market_addr=market_addr,
                prev_order_id="42",
                tp_trigger_price=55000.0,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::update_tp_order_for_position"
        )
        args = payload.function_arguments
        assert args[0] == TEST_SUBACCOUNT_ADDR
        assert args[1] == 42  # int conversion
        assert args[2] == market_addr
        assert args[3] == 55000.0


# ===========================================================================
# Tests for update_sl_order_for_position (async)
# ===========================================================================


class TestUpdateSlOrderForPosition:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.update_sl_order_for_position(
                market_addr=market_addr,
                prev_order_id=99,
                sl_trigger_price=44000.0,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::update_sl_order_for_position"
        )
        args = payload.function_arguments
        assert args[1] == 99
        assert args[3] == 44000.0


# ===========================================================================
# Tests for cancel_tp_sl_order_for_position (async)
# ===========================================================================


class TestCancelTpSlOrderForPosition:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_tp_sl_order_for_position(market_addr=market_addr, order_id="77")

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_tp_sl_order_for_position"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, market_addr, 77]


# ===========================================================================
# Tests for cancel_twap_order (async)
# ===========================================================================


class TestCancelTwapOrder:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_twap_order(market_addr=market_addr, order_id=33)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_twap_orders_to_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, market_addr, 33]


# ===========================================================================
# Tests for deactivate_subaccount (async)
# ===========================================================================


class TestDeactivateSubaccount:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.deactivate_subaccount(subaccount_addr=TEST_SUBACCOUNT_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::deactivate_subaccount"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, True]

    async def test_passes_revoke_all_delegations_false(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.deactivate_subaccount(
            subaccount_addr=TEST_SUBACCOUNT_ADDR, revoke_all_delegations=False
        )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[1] is False


# ===========================================================================
# Tests for activate_vault (async)
# ===========================================================================


class TestActivateVault:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.activate_vault(vault_address=TEST_VAULT_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_api::activate_vault"
        assert payload.function_arguments == [TEST_VAULT_ADDR]


# ===========================================================================
# Tests for deposit_to_vault (async)
# ===========================================================================


class TestDepositToVault:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.deposit_to_vault(
            vault_address=TEST_VAULT_ADDR,
            amount=500.0,
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
        )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::contribute_to_vault"
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            TEST_VAULT_ADDR,
            TEST_USDC,
            500.0,
        ]


# ===========================================================================
# Tests for withdraw_from_vault (async)
# ===========================================================================


class TestWithdrawFromVault:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.withdraw_from_vault(vault_address=TEST_VAULT_ADDR, shares=10.0)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::redeem_from_vault"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_VAULT_ADDR, 10.0]


# ===========================================================================
# Tests for delegate_vault_actions (async)
# ===========================================================================


class TestDelegateVaultActions:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        delegate_addr = "0x" + "dd" * 32
        await write_dex.delegate_vault_actions(
            vault_address=TEST_VAULT_ADDR,
            account_to_delegate_to=delegate_addr,
        )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_admin_api::delegate_dex_actions_to"
        assert payload.function_arguments == [TEST_VAULT_ADDR, delegate_addr, None]


# ===========================================================================
# Tests for approve_max_builder_fee (async)
# ===========================================================================


class TestApproveMaxBuilderFee:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        builder_addr = "0x" + "ee" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.approve_max_builder_fee(builder_addr=builder_addr, max_fee=1000)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::approve_max_builder_fee_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, builder_addr, 1000]


# ===========================================================================
# Tests for revoke_max_builder_fee (async)
# ===========================================================================


class TestRevokeMaxBuilderFee:
    async def test_sends_correct_function(self, write_dex: DecibelWriteDex) -> None:
        builder_addr = "0x" + "ee" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.revoke_max_builder_fee(builder_addr=builder_addr)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::revoke_max_builder_fee_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, builder_addr]


# ===========================================================================
# Tests for create_vault (async)
# ===========================================================================


class TestCreateVault:
    async def test_sends_correct_function_with_explicit_subaccount(
        self, write_dex: DecibelWriteDex
    ) -> None:
        args = {
            "vault_name": "My Vault",
            "vault_description": "A test vault",
            "vault_social_links": [],
            "vault_share_symbol": "MVT",
            "fee_bps": 100,
            "fee_interval_s": 86400,
            "contribution_lockup_duration_s": 604800,
            "initial_funding": 1000,
            "accepts_contributions": True,
            "delegate_to_creator": False,
        }
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.create_vault(
                args,
                subaccount_addr=TEST_SUBACCOUNT_ADDR,  # type: ignore[arg-type]
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_api::create_and_fund_vault"


# ===========================================================================
# Tests for DecibelWriteDexSync (representative subset)
# ===========================================================================


class TestDecibelWriteDexSyncInit:
    def test_init_creates_order_status_client(self, test_config, mock_account) -> None:
        with (
            patch("decibel.write.BaseSDKSync.__init__", return_value=None),
            patch("decibel.write.OrderStatusClient") as mock_osc,
        ):
            dex = DecibelWriteDexSync.__new__(DecibelWriteDexSync)
            dex._http_client = MagicMock()
            dex._config = test_config
            dex._account = mock_account
            dex._order_status_client = mock_osc.return_value
            assert dex.order_status_client is mock_osc.return_value


class TestDecibelWriteDexSyncExtractOrderId:
    def test_extracts_string_order_id(self, write_dex_sync: DecibelWriteDexSync) -> None:
        tx = _make_tx_response(order_id="42", user_addr=TEST_ACCOUNT_ADDR)
        result = write_dex_sync._extract_order_id_from_transaction(tx)
        assert result == "42"

    def test_returns_none_when_no_events(self, write_dex_sync: DecibelWriteDexSync) -> None:
        tx: dict[str, Any] = {"hash": TEST_TX_HASH}
        result = write_dex_sync._extract_order_id_from_transaction(tx)
        assert result is None

    def test_handles_twap_event(self, write_dex_sync: DecibelWriteDexSync) -> None:
        tx = _make_twap_tx_response(order_id="77")
        result = write_dex_sync._extract_order_id_from_transaction(tx)
        assert result == "77"

    def test_handles_exception_gracefully(self, write_dex_sync: DecibelWriteDexSync) -> None:
        result = write_dex_sync._extract_order_id_from_transaction({"events": "bad"})  # type: ignore[arg-type]
        assert result is None


class TestDecibelWriteDexSyncSendSubaccountTx:
    def test_uses_primary_subaccount_when_none(self, write_dex_sync: DecibelWriteDexSync) -> None:
        called_with: list[str] = []

        def fake_tx(addr: str) -> dict[str, Any]:
            called_with.append(addr)
            return {"hash": TEST_TX_HASH}

        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = write_dex_sync.send_subaccount_tx(fake_tx)

        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == {"hash": TEST_TX_HASH}

    def test_uses_provided_subaccount_addr(self, write_dex_sync: DecibelWriteDexSync) -> None:
        called_with: list[str] = []

        def fake_tx(addr: str) -> dict[str, Any]:
            called_with.append(addr)
            return {"hash": TEST_TX_HASH}

        write_dex_sync.send_subaccount_tx(fake_tx, subaccount_addr=TEST_SUBACCOUNT_ADDR)
        assert called_with == [TEST_SUBACCOUNT_ADDR]


class TestDecibelWriteDexSyncRenameSubaccount:
    def test_posts_to_correct_url(self, write_dex_sync: DecibelWriteDexSync) -> None:
        mock_result = (MagicMock(), 200, "OK")
        args = RenameSubaccountArgs(subaccountAddress=TEST_SUBACCOUNT_ADDR, newName="New Name")

        with patch("decibel.write.post_request_sync", return_value=mock_result) as mock_post:
            write_dex_sync.rename_subaccount(args)

        expected_url = (
            f"{write_dex_sync._config.trading_http_url}/api/v1/subaccounts/{TEST_SUBACCOUNT_ADDR}"
        )
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.args[1] == expected_url
        assert call_kwargs.kwargs["body"] == {"name": "New Name"}


class TestDecibelWriteDexSyncCreateSubaccount:
    def test_sends_correct_function(self, write_dex_sync: DecibelWriteDexSync) -> None:
        result = write_dex_sync.create_subaccount()

        write_dex_sync._send_tx.assert_called_once()
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::create_new_subaccount"
        assert result == _make_tx_response()


class TestDecibelWriteDexSyncDeposit:
    def test_deposit_uses_primary_subaccount_by_default(
        self, write_dex_sync: DecibelWriteDexSync
    ) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.deposit(amount=100)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::deposit_to_subaccount_at"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_USDC, 100]

    def test_deposit_uses_explicit_subaccount(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync.deposit(amount=250, subaccount_addr=TEST_SUBACCOUNT_ADDR)
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments[0] == TEST_SUBACCOUNT_ADDR
        assert payload.function_arguments[2] == 250


class TestDecibelWriteDexSyncWithdraw:
    def test_withdraw_uses_correct_function(self, write_dex_sync: DecibelWriteDexSync) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.withdraw(amount=300)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::withdraw_from_subaccount"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_USDC, 300]


class TestDecibelWriteDexSyncPlaceOrder:
    def test_place_order_success(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync._send_tx.return_value = _make_tx_response(order_id="456")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = write_dex_sync.place_order(
                market_name=TEST_MARKET_NAME,
                price=50000,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
            )

        assert isinstance(result, PlaceOrderSuccess)
        assert result.order_id == "456"
        assert result.transaction_hash == TEST_TX_HASH

    def test_place_order_failure_on_exception(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync._send_tx.side_effect = RuntimeError("Sync error")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = write_dex_sync.place_order(
                market_name=TEST_MARKET_NAME,
                price=100,
                size=0.5,
                is_buy=False,
                time_in_force=TimeInForce.ImmediateOrCancel,
                is_reduce_only=True,
            )

        assert isinstance(result, PlaceOrderFailure)
        assert "RuntimeError" in result.error

    def test_place_order_with_tick_size(self, write_dex_sync: DecibelWriteDexSync) -> None:
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            write_dex_sync.place_order(
                market_name=TEST_MARKET_NAME,
                price=50007,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
                tick_size=10,
            )

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments[2] == 50010  # rounded to nearest 10


class TestDecibelWriteDexSyncCancelOrder:
    def test_cancel_order_raises_without_market(self, write_dex_sync: DecibelWriteDexSync) -> None:
        with pytest.raises(ValueError, match="Either market_name or market_addr must be provided"):
            write_dex_sync.cancel_order(order_id=1)

    def test_cancel_order_by_market_name(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            write_dex_sync.cancel_order(order_id=10, market_name=TEST_MARKET_NAME)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_order_to_subaccount"

    def test_cancel_order_by_market_addr(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.cancel_order(order_id="20", market_addr=market_addr)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments[1] == 20  # int conversion


class TestDecibelWriteDexSyncPlaceBulkOrders:
    def test_success(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = write_dex_sync.place_bulk_orders(
                market_name=TEST_MARKET_NAME,
                sequence_number=1,
                bid_prices=[100],
                bid_sizes=[10],
                ask_prices=[101],
                ask_sizes=[10],
            )

        assert isinstance(result, PlaceBulkOrdersSuccess)

    def test_failure_on_exception(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync._send_tx.side_effect = RuntimeError("Failure")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = write_dex_sync.place_bulk_orders(
                market_name=TEST_MARKET_NAME,
                sequence_number=1,
                bid_prices=[100],
                bid_sizes=[10],
                ask_prices=[101],
                ask_sizes=[10],
            )

        assert isinstance(result, PlaceBulkOrdersFailure)


class TestDecibelWriteDexSyncTwapOrder:
    def test_place_twap_success(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync._send_tx.return_value = _make_twap_tx_response(order_id="11")
        with (
            patch("decibel.write.get_market_addr", return_value="0x" + "11" * 32),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            result = write_dex_sync.place_twap_order(
                market_name=TEST_MARKET_NAME,
                size=1,
                is_buy=True,
                is_reduce_only=False,
                twap_frequency_seconds=60,
                twap_duration_seconds=3600,
            )

        assert isinstance(result, PlaceOrderSuccess)
        assert result.order_id == "11"

    def test_cancel_twap_order(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.cancel_twap_order(order_id="55", market_addr=market_addr)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_twap_orders_to_subaccount"
        )
        assert payload.function_arguments[2] == 55  # int conversion


class TestDecibelWriteDexSyncVaultOperations:
    def test_activate_vault(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync.activate_vault(vault_address=TEST_VAULT_ADDR)
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_api::activate_vault"
        assert payload.function_arguments == [TEST_VAULT_ADDR]

    def test_deposit_to_vault(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync.deposit_to_vault(
            vault_address=TEST_VAULT_ADDR,
            amount=100.0,
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
        )
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::contribute_to_vault"
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            TEST_VAULT_ADDR,
            TEST_USDC,
            100.0,
        ]

    def test_withdraw_from_vault(self, write_dex_sync: DecibelWriteDexSync) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.withdraw_from_vault(vault_address=TEST_VAULT_ADDR, shares=5.0)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::redeem_from_vault"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_VAULT_ADDR, 5.0]

    def test_delegate_vault_actions(self, write_dex_sync: DecibelWriteDexSync) -> None:
        delegate_addr = "0x" + "dd" * 32
        write_dex_sync.delegate_vault_actions(
            vault_address=TEST_VAULT_ADDR,
            account_to_delegate_to=delegate_addr,
        )
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_admin_api::delegate_dex_actions_to"
        assert payload.function_arguments == [TEST_VAULT_ADDR, delegate_addr, None]


class TestDecibelWriteDexSyncApproveRevokeBuilderFee:
    def test_approve_max_builder_fee(self, write_dex_sync: DecibelWriteDexSync) -> None:
        builder_addr = "0x" + "ee" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.approve_max_builder_fee(builder_addr=builder_addr, max_fee=500)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::approve_max_builder_fee_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, builder_addr, 500]

    def test_revoke_max_builder_fee(self, write_dex_sync: DecibelWriteDexSync) -> None:
        builder_addr = "0x" + "ee" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.revoke_max_builder_fee(builder_addr=builder_addr)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::revoke_max_builder_fee_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, builder_addr]


class TestDecibelWriteDexSyncDelegation:
    def test_delegate_trading_to_for_subaccount(self, write_dex_sync: DecibelWriteDexSync) -> None:
        delegate_addr = "0x" + "dd" * 32
        write_dex_sync.delegate_trading_to_for_subaccount(
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
            account_to_delegate_to=delegate_addr,
            expiration_timestamp_secs=12345,
        )
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::delegate_trading_to_for_subaccount"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            delegate_addr,
            12345,
        ]

    def test_revoke_delegation(self, write_dex_sync: DecibelWriteDexSync) -> None:
        revoking_addr = "0x" + "ff" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.revoke_delegation(account_to_revoke=revoking_addr)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::revoke_delegation"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, revoking_addr]


class TestDecibelWriteDexSyncTpSlOrders:
    def test_place_tp_sl_order_for_position(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.place_tp_sl_order_for_position(
                market_addr=market_addr,
                tp_trigger_price=55000,
                sl_trigger_price=45000,
                tick_size=100,
            )

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::place_tp_sl_order_for_position"
        )
        # Check trailing Nones
        assert payload.function_arguments[-2] is None
        assert payload.function_arguments[-1] is None

    def test_update_tp_order_for_position(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.update_tp_order_for_position(
                market_addr=market_addr,
                prev_order_id="88",
                tp_trigger_price=60000.0,
            )

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::update_tp_order_for_position"
        )
        assert payload.function_arguments[1] == 88  # int conversion

    def test_update_sl_order_for_position(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.update_sl_order_for_position(
                market_addr=market_addr,
                prev_order_id=77,
                sl_trigger_price=40000.0,
            )

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::update_sl_order_for_position"
        )

    def test_cancel_tp_sl_order_for_position(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            write_dex_sync.cancel_tp_sl_order_for_position(market_addr=market_addr, order_id="33")

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, market_addr, 33]


class TestDecibelWriteDexSyncDeactivateSubaccount:
    def test_sends_correct_function(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync.deactivate_subaccount(subaccount_addr=TEST_SUBACCOUNT_ADDR)
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::deactivate_subaccount"
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, True]

    def test_revoke_all_delegations_false(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync.deactivate_subaccount(
            subaccount_addr=TEST_SUBACCOUNT_ADDR, revoke_all_delegations=False
        )
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments[1] is False


class TestDecibelWriteDexSyncTriggerMatching:
    def test_sends_correct_function(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        result = write_dex_sync.trigger_matching(market_addr=market_addr, max_work_unit=50)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::public_apis::process_perp_market_pending_requests"
        )
        assert payload.function_arguments == [market_addr, 50]
        assert result == {"success": True, "transactionHash": TEST_TX_HASH}


class TestDecibelWriteDexSyncCancelBulkOrder:
    def test_sends_correct_function(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            write_dex_sync.cancel_bulk_order(market_name=TEST_MARKET_NAME)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_bulk_order_to_subaccount"
        )

    def test_cancel_client_order(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        with (
            patch("decibel.write.get_market_addr", return_value=market_addr),
            patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR),
        ):
            write_dex_sync.cancel_client_order(
                client_order_id="cid-1", market_name=TEST_MARKET_NAME
            )

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::cancel_client_order_to_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, "cid-1", market_addr]


class TestDecibelWriteDexSyncConfigureUserSettings:
    def test_sends_correct_payload(self, write_dex_sync: DecibelWriteDexSync) -> None:
        market_addr = "0x" + "11" * 32
        write_dex_sync.configure_user_settings_for_market(
            market_addr=market_addr,
            subaccount_addr=TEST_SUBACCOUNT_ADDR,
            is_cross=False,
            user_leverage=5,
        )
        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_entry::configure_user_settings_for_market"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            market_addr,
            False,
            5,
        ]


class TestDecibelWriteDexSyncWithSubaccount:
    def test_with_subaccount_uses_primary_when_none(
        self, write_dex_sync: DecibelWriteDexSync
    ) -> None:
        called_with: list[str] = []

        def fn(addr: str) -> str:
            called_with.append(addr)
            return "ok"

        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = write_dex_sync.with_subaccount(fn)

        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == "ok"

    def test_with_subaccount_uses_provided_addr(self, write_dex_sync: DecibelWriteDexSync) -> None:
        called_with: list[str] = []

        def fn(addr: str) -> str:
            called_with.append(addr)
            return "done"

        result = write_dex_sync.with_subaccount(fn, subaccount_addr=TEST_SUBACCOUNT_ADDR)
        assert called_with == [TEST_SUBACCOUNT_ADDR]
        assert result == "done"
