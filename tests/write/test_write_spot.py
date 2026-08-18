"""Unit tests for the spot + campaign/FFT write surface.

Same strategy as ``test_write_dex.py``: ``_send_tx`` is mocked at the instance level, so the
tests assert on the assembled Move function name and argument order rather than on chain state.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from decibel._order_types import PlaceSpotOrderFailure, PlaceSpotOrderSuccess
from decibel._utils import get_spot_market_addr
from decibel.write import (
    DecibelWriteDex,
    DecibelWriteDexSync,
    TimeInForce,
    _round_price_to_tick_for_side,  # type: ignore[attr-defined]
)

if TYPE_CHECKING:
    from decibel._constants import DecibelConfig
    from decibel._transaction_builder import InputEntryFunctionData

TEST_PACKAGE = "0x" + "ab" * 32
TEST_ACCOUNT_ADDR = "0x" + "aa" * 32
TEST_SUBACCOUNT_ADDR = "0x" + "bb" * 32
TEST_MARKET_ADDR = "0x" + "dd" * 32
TEST_BUILDER_ADDR = "0x" + "ee" * 32
TEST_ASSET_ADDR = "0x" + "f1" * 32
TEST_CAMPAIGN_PACKAGE = "0x" + "c0" * 32
TEST_TX_HASH = "0xdeadbeef"
TEST_SPOT_MARKET_NAME = "APT/USDC"


def _order_event_response(
    order_id: str = "777",
    user_addr: str = TEST_SUBACCOUNT_ADDR,
) -> dict[str, Any]:
    return {
        "hash": TEST_TX_HASH,
        "success": True,
        "events": [
            {
                "type": "0x1::market_types::OrderEvent",
                "data": {"user": user_addr, "order_id": order_id},
            }
        ],
    }


def _pending_cbs_response(
    order_id: str = "888",
    subaccount_addr: str = TEST_SUBACCOUNT_ADDR,
) -> dict[str, Any]:
    return {
        "hash": TEST_TX_HASH,
        "success": True,
        "events": [
            {
                "type": f"{TEST_PACKAGE}::spot_pending_cbs_queue::SpotOrderPendingCbsEvent",
                "data": {"subaccount_addr": subaccount_addr, "order_id": order_id},
            }
        ],
    }


@pytest.fixture
def write_dex(test_config: DecibelConfig, mock_account: MagicMock) -> DecibelWriteDex:
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
        dex._send_tx = AsyncMock(return_value=_order_event_response())
        return dex


@pytest.fixture
def write_dex_sync(test_config: DecibelConfig, mock_account: MagicMock) -> DecibelWriteDexSync:
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
        dex._send_tx = MagicMock(return_value=_order_event_response())
        return dex


# ===========================================================================
# _round_price_to_tick_for_side
# ===========================================================================


class TestRoundToTickSizeForSide:
    def test_buy_rounds_down(self) -> None:
        # A buy must never end up above the caller's cap.
        assert _round_price_to_tick_for_side(10.7, 0.5, is_buy=True) == pytest.approx(10.5)

    def test_sell_rounds_up(self) -> None:
        # A sell must never end up below the caller's floor.
        assert _round_price_to_tick_for_side(10.7, 0.5, is_buy=False) == pytest.approx(11.0)

    @pytest.mark.parametrize("is_buy", [True, False])
    def test_already_aligned_price_is_unchanged(self, is_buy: bool) -> None:
        # The epsilon exists so float division noise doesn't nudge an aligned price a full tick.
        assert _round_price_to_tick_for_side(10.5, 0.1, is_buy=is_buy) == pytest.approx(10.5)

    @pytest.mark.parametrize("is_buy", [True, False])
    def test_zero_inputs(self, is_buy: bool) -> None:
        assert _round_price_to_tick_for_side(0, 0.5, is_buy=is_buy) == 0.0
        assert _round_price_to_tick_for_side(10.7, 0, is_buy=is_buy) == 0.0


# ===========================================================================
# Market address resolution
# ===========================================================================


class TestSpotMarketResolution:
    async def test_market_name_uses_spot_derivation(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_spot_order(order_id=1, market_name=TEST_SPOT_MARKET_NAME)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        # Spot markets hang off the package's GlobalSpotEngine, NOT perp_engine_global.
        assert payload.function_arguments[1] == get_spot_market_addr(
            TEST_SPOT_MARKET_NAME, TEST_PACKAGE
        )

    async def test_market_addr_is_used_verbatim(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_spot_order(order_id=1, market_addr=TEST_MARKET_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[1] == TEST_MARKET_ADDR

    async def test_neither_reference_raises(self, write_dex: DecibelWriteDex) -> None:
        with pytest.raises(ValueError, match="market_name or market_addr"):
            await write_dex.cancel_spot_order(order_id=1)


# ===========================================================================
# place_spot_order
# ===========================================================================


class TestPlaceSpotOrder:
    async def test_sends_correct_payload(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                builder_addr=TEST_BUILDER_ADDR,
                builder_fee=10,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_spot_entry::place_spot_order_to_subaccount"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            TEST_MARKET_ADDR,
            100,
            5,
            True,
            TimeInForce.GoodTillCanceled,
            TEST_BUILDER_ADDR,
            1000,  # bps_to_chain_units(10)
        ]
        assert isinstance(result, PlaceSpotOrderSuccess)
        assert result.order_id == "777"
        assert result.pending_cbs is False
        assert result.transaction_hash == TEST_TX_HASH

    async def test_builder_fee_omitted_stays_none(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.ImmediateOrCancel,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[6] is None
        assert payload.function_arguments[7] is None

    async def test_tick_size_rounds_side_safe(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=10.7,
                size=1,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                tick_size=0.5,
            )
        buy_payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert buy_payload.function_arguments[2] == pytest.approx(10.5)

        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=10.7,
                size=1,
                is_buy=False,
                time_in_force=TimeInForce.GoodTillCanceled,
                tick_size=0.5,
            )
        sell_payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert sell_payload.function_arguments[2] == pytest.approx(11.0)

    async def test_pending_cbs_event_is_reported(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.return_value = _pending_cbs_response(order_id="888")
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
            )

        assert isinstance(result, PlaceSpotOrderSuccess)
        # The tx committed, but the order is queued behind a CBS withdrawal, not on the book.
        assert result.pending_cbs is True
        assert result.order_id == "888"

    async def test_event_for_a_different_subaccount_is_ignored(
        self, write_dex: DecibelWriteDex
    ) -> None:
        write_dex._send_tx.return_value = _order_event_response(user_addr="0x" + "99" * 32)
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
            )

        assert isinstance(result, PlaceSpotOrderSuccess)
        assert result.order_id is None
        assert result.pending_cbs is False

    async def test_short_form_event_address_still_matches(self, write_dex: DecibelWriteDex) -> None:
        # Nodes return addresses without leading zeros; comparison must normalize both sides.
        full = "0x" + "0" * 63 + "1"
        write_dex._send_tx.return_value = _order_event_response(user_addr="0x1")
        with patch("decibel.write.get_primary_subaccount_addr", return_value=full):
            result = await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                subaccount_addr=full,
            )

        assert isinstance(result, PlaceSpotOrderSuccess)
        assert result.order_id == "777"

    async def test_failure_is_returned_not_raised(self, write_dex: DecibelWriteDex) -> None:
        write_dex._send_tx.side_effect = RuntimeError("simulation failed")
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = await write_dex.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
            )

        assert isinstance(result, PlaceSpotOrderFailure)
        assert result.error == "RuntimeError: simulation failed"

    def test_sync_mirrors_async(self, write_dex_sync: DecibelWriteDexSync) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            result = write_dex_sync.place_spot_order(
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=5,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
            )

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_spot_entry::place_spot_order_to_subaccount"
        )
        assert isinstance(result, PlaceSpotOrderSuccess)
        assert result.order_id == "777"


# ===========================================================================
# Remaining spot entry points
# ===========================================================================


class TestSpotEntryFunctions:
    async def test_cancel_spot_order(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_spot_order(order_id="42", market_addr=TEST_MARKET_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_spot_entry::cancel_spot_order_to_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_MARKET_ADDR, 42]

    async def test_place_spot_bulk_order(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.place_spot_bulk_order(
                market_addr=TEST_MARKET_ADDR,
                sequence_number=7,
                bid_prices=[100, 99],
                bid_sizes=[1, 2],
                ask_prices=[101, 102],
                ask_sizes=[3, 4],
                builder_addr=TEST_BUILDER_ADDR,
                builder_fee=5,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_spot_entry::place_spot_bulk_order_to_subaccount"
        )
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            TEST_MARKET_ADDR,
            7,
            [100, 99],
            [1, 2],
            [101, 102],
            [3, 4],
            TEST_BUILDER_ADDR,
            500,
        ]

    async def test_cancel_spot_bulk_order(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_spot_bulk_order(market_addr=TEST_MARKET_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_spot_entry::cancel_spot_bulk_order_to_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_MARKET_ADDR]

    async def test_cancel_spot_bulk_order_at_price_level(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.cancel_spot_bulk_order_at_price_level(
                market_addr=TEST_MARKET_ADDR, price=100, is_buy=True
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == (
            f"{TEST_PACKAGE}::dex_accounts_spot_entry"
            "::cancel_spot_bulk_order_at_price_level_to_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_MARKET_ADDR, 100, True]

    async def test_approve_max_spot_builder_fee(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.approve_max_spot_builder_fee(
                builder_addr=TEST_BUILDER_ADDR, max_fee=1000
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == (
            f"{TEST_PACKAGE}::dex_accounts_spot_entry::approve_max_spot_builder_fee_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_BUILDER_ADDR, 100000]

    async def test_revoke_max_spot_builder_fee(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.revoke_max_spot_builder_fee(builder_addr=TEST_BUILDER_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == (
            f"{TEST_PACKAGE}::dex_accounts_spot_entry::revoke_max_spot_builder_fee_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_BUILDER_ADDR]

    async def test_set_hold_as_non_collateral(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.set_hold_as_non_collateral(asset_addr=TEST_ASSET_ADDR, hold=True)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == (
            f"{TEST_PACKAGE}::dex_accounts_spot_entry::set_hold_as_non_collateral_for_subaccount"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_ASSET_ADDR, True]

    async def test_process_spot_pending_requests_takes_no_subaccount(
        self, write_dex: DecibelWriteDex
    ) -> None:
        await write_dex.process_spot_pending_requests(market_addr=TEST_MARKET_ADDR, max_fills=25)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::dex_accounts_spot_entry::process_spot_pending_requests"
        )
        # Permissionless crank: market + max_fills only, no subaccount prefix.
        assert payload.function_arguments == [TEST_MARKET_ADDR, 25]

    @pytest.mark.parametrize(
        ("method", "kwargs", "expected_fn"),
        [
            (
                "cancel_spot_order",
                {"order_id": 42, "market_addr": TEST_MARKET_ADDR},
                "cancel_spot_order_to_subaccount",
            ),
            (
                "cancel_spot_bulk_order",
                {"market_addr": TEST_MARKET_ADDR},
                "cancel_spot_bulk_order_to_subaccount",
            ),
            (
                "cancel_spot_bulk_order_at_price_level",
                {"market_addr": TEST_MARKET_ADDR, "price": 100, "is_buy": False},
                "cancel_spot_bulk_order_at_price_level_to_subaccount",
            ),
            (
                "approve_max_spot_builder_fee",
                {"builder_addr": TEST_BUILDER_ADDR, "max_fee": 1000},
                "approve_max_spot_builder_fee_for_subaccount",
            ),
            (
                "revoke_max_spot_builder_fee",
                {"builder_addr": TEST_BUILDER_ADDR},
                "revoke_max_spot_builder_fee_for_subaccount",
            ),
            (
                "set_hold_as_non_collateral",
                {"asset_addr": TEST_ASSET_ADDR, "hold": False},
                "set_hold_as_non_collateral_for_subaccount",
            ),
            (
                "process_spot_pending_requests",
                {"market_addr": TEST_MARKET_ADDR, "max_fills": 10},
                "process_spot_pending_requests",
            ),
        ],
    )
    def test_sync_mirrors_every_spot_entry(
        self,
        write_dex_sync: DecibelWriteDexSync,
        method: str,
        kwargs: dict[str, Any],
        expected_fn: str,
    ) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            getattr(write_dex_sync, method)(**kwargs)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_spot_entry::{expected_fn}"


# ===========================================================================
# Non-spot parity methods
# ===========================================================================


class TestParityWrites:
    async def test_withdraw_non_collateral(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.withdraw_non_collateral(TEST_ASSET_ADDR, 500)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::withdraw_from_non_collateral"
        )
        assert payload.function_arguments == [TEST_SUBACCOUNT_ADDR, TEST_ASSET_ADDR, 500]

    async def test_admin_create_subaccount(self, write_dex: DecibelWriteDex) -> None:
        await write_dex.admin_create_subaccount(TEST_ACCOUNT_ADDR)

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::admin_create_new_subaccount"
        )
        assert payload.function_arguments == [TEST_ACCOUNT_ADDR]

    async def test_update_order_argument_order(self, write_dex: DecibelWriteDex) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            await write_dex.update_order(
                order_id="9",
                market_addr=TEST_MARKET_ADDR,
                price=100,
                size=2,
                is_buy=True,
                time_in_force=TimeInForce.PostOnly,
                is_reduce_only=False,
                tp_trigger_price=120,
                tp_limit_price=119,
            )

        payload: InputEntryFunctionData = write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::update_order_to_subaccount"
        # Omitted sl_* legs are Option::None, i.e. they are *removed* from the order.
        assert payload.function_arguments == [
            TEST_SUBACCOUNT_ADDR,
            9,
            TEST_MARKET_ADDR,
            100,
            2,
            True,
            TimeInForce.PostOnly,
            False,
            120,
            119,
            None,
            None,
            None,
            None,
        ]

    @pytest.mark.parametrize(
        ("method", "kwargs", "expected_fn"),
        [
            (
                "withdraw_non_collateral",
                {"asset_addr": TEST_ASSET_ADDR, "amount": 500},
                "withdraw_from_non_collateral",
            ),
            (
                "admin_create_subaccount",
                {"owner_address": TEST_ACCOUNT_ADDR},
                "admin_create_new_subaccount",
            ),
        ],
    )
    def test_sync_mirrors_parity_writes(
        self,
        write_dex_sync: DecibelWriteDexSync,
        method: str,
        kwargs: dict[str, Any],
        expected_fn: str,
    ) -> None:
        with patch("decibel.write.get_primary_subaccount_addr", return_value=TEST_SUBACCOUNT_ADDR):
            getattr(write_dex_sync, method)(**kwargs)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::dex_accounts_entry::{expected_fn}"


# ===========================================================================
# Campaign / funded-first-trade
# ===========================================================================


@pytest.fixture
def campaign_write_dex(write_dex: DecibelWriteDex) -> DecibelWriteDex:
    write_dex._config = dataclasses.replace(
        write_dex._config,
        deployment=dataclasses.replace(
            write_dex._config.deployment, campaign_package=TEST_CAMPAIGN_PACKAGE
        ),
    )
    return write_dex


class TestCampaignAndFft:
    async def test_missing_campaign_package_raises(self, write_dex: DecibelWriteDex) -> None:
        # The default test deployment has no campaign package configured.
        with pytest.raises(ValueError, match="no campaign package"):
            await write_dex.claim_campaign_reward(1)

    async def test_claim_campaign_reward(self, campaign_write_dex: DecibelWriteDex) -> None:
        await campaign_write_dex.claim_campaign_reward(7)

        payload: InputEntryFunctionData = campaign_write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_CAMPAIGN_PACKAGE}::campaign_manager::claim_by_id"
        # u64 on the wire as a decimal string, matching the FFT payload builders.
        assert payload.function_arguments == ["7"]

    async def test_open_fft_trial_defaults_campaign_addr_to_package(
        self, campaign_write_dex: DecibelWriteDex
    ) -> None:
        await campaign_write_dex.open_fft_trial(owner=TEST_ACCOUNT_ADDR)

        payload: InputEntryFunctionData = campaign_write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_CAMPAIGN_PACKAGE}::funded_first_trade::open_trial"
        assert payload.function_arguments == [TEST_CAMPAIGN_PACKAGE, TEST_ACCOUNT_ADDR]

    async def test_explicit_campaign_addr_overrides(
        self, campaign_write_dex: DecibelWriteDex
    ) -> None:
        campaign_addr = "0x" + "5a" * 32
        await campaign_write_dex.open_fft_trial(
            owner=TEST_ACCOUNT_ADDR, campaign_addr=campaign_addr
        )

        payload: InputEntryFunctionData = campaign_write_dex._send_tx.call_args.args[0]
        assert payload.function_arguments == [campaign_addr, TEST_ACCOUNT_ADDR]

    async def test_claim_fft_unlock(self, campaign_write_dex: DecibelWriteDex) -> None:
        await campaign_write_dex.claim_fft_unlock(lock_id=12, owner=TEST_ACCOUNT_ADDR)

        payload: InputEntryFunctionData = campaign_write_dex._send_tx.call_args.args[0]
        # The on-chain entry is named `unlock`, not `claim_unlock`.
        assert payload.function == f"{TEST_CAMPAIGN_PACKAGE}::funded_first_trade::unlock"
        # u64 args go over the wire as strings.
        assert payload.function_arguments == [TEST_CAMPAIGN_PACKAGE, "12", TEST_ACCOUNT_ADDR]

    async def test_settle_fft_trial(self, campaign_write_dex: DecibelWriteDex) -> None:
        await campaign_write_dex.settle_fft_trial(trial_id=3)

        payload: InputEntryFunctionData = campaign_write_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_CAMPAIGN_PACKAGE}::funded_first_trade::settle_trial"
        assert payload.function_arguments == [TEST_CAMPAIGN_PACKAGE, "3"]

    def test_sync_claim_campaign_reward(self, write_dex_sync: DecibelWriteDexSync) -> None:
        write_dex_sync._config = dataclasses.replace(
            write_dex_sync._config,
            deployment=dataclasses.replace(
                write_dex_sync._config.deployment, campaign_package=TEST_CAMPAIGN_PACKAGE
            ),
        )
        write_dex_sync.claim_campaign_reward(7)

        payload: InputEntryFunctionData = write_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_CAMPAIGN_PACKAGE}::campaign_manager::claim_by_id"
