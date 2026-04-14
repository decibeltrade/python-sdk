"""
Comprehensive unit tests for src/decibel/admin.py.

Tests cover DecibelAdminDex (async) and DecibelAdminDexSync (sync) classes.

Strategy: mock _send_tx at the instance level so no real HTTP calls or
blockchain interactions happen. The tests verify that:
  1. The correct Move function name is assembled from the package address.
  2. The correct arguments are passed to InputEntryFunctionData.
  3. usdc_balance works for both AccountAddress and str inputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aptos_sdk.account_address import AccountAddress

from decibel.admin import DecibelAdminDex, DecibelAdminDexSync

if TYPE_CHECKING:
    from decibel._transaction_builder import InputEntryFunctionData

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TEST_PACKAGE = "0x" + "ab" * 32
TEST_USDC = "0x" + "cd" * 32
TEST_PERP_ENGINE = "0x" + "12" * 32
TEST_ACCOUNT_ADDR = "0x" + "aa" * 32
TEST_TX_HASH = "0xdeadbeef"
TEST_MARKET_NAME = "ETH-USD"
TEST_MARKET_ADDR = "0x" + "11" * 32
TEST_VAULT_ADDR = "0x" + "cc" * 32
TEST_COLLATERAL_ADDR = "0x" + "dd" * 32
TEST_BACKSTOP_ADDR = "0x" + "ee" * 32
TEST_DELEGATE_ADDR = "0x" + "ff" * 32


def _make_tx_response(hash_val: str = TEST_TX_HASH) -> dict[str, Any]:
    return {"hash": hash_val, "success": True, "events": []}


# ---------------------------------------------------------------------------
# Fixtures – async (DecibelAdminDex)
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_dex(test_config, mock_account) -> DecibelAdminDex:
    """Return a DecibelAdminDex instance with _send_tx mocked out."""
    with patch("decibel.admin.BaseSDK.__init__", return_value=None):
        dex = DecibelAdminDex.__new__(DecibelAdminDex)
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
        dex._send_tx = AsyncMock(return_value=_make_tx_response())
        dex._aptos = AsyncMock()
        return dex


# ---------------------------------------------------------------------------
# Fixtures – sync (DecibelAdminDexSync)
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_dex_sync(test_config, mock_account) -> DecibelAdminDexSync:
    """Return a DecibelAdminDexSync instance with _send_tx mocked out."""
    with patch("decibel.admin.BaseSDKSync.__init__", return_value=None):
        dex = DecibelAdminDexSync.__new__(DecibelAdminDexSync)
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
        dex._send_tx = MagicMock(return_value=_make_tx_response())
        dex._owns_http_client = False
        return dex


# ===========================================================================
# Tests for DecibelAdminDex.__init__
# ===========================================================================


class TestDecibelAdminDexInit:
    def test_init_calls_super(self, test_config, mock_account) -> None:
        with patch("decibel.admin.BaseSDK.__init__") as mock_super:
            mock_super.return_value = None
            dex = DecibelAdminDex.__new__(DecibelAdminDex)
            DecibelAdminDex.__init__(dex, test_config, mock_account)
            mock_super.assert_called_once_with(test_config, mock_account, None)


# ===========================================================================
# Tests for get_protocol_vault_address (async)
# ===========================================================================


class TestGetProtocolVaultAddress:
    def test_returns_account_address(self, admin_dex: DecibelAdminDex) -> None:
        result = admin_dex.get_protocol_vault_address()
        assert isinstance(result, AccountAddress)

    def test_is_deterministic(self, admin_dex: DecibelAdminDex) -> None:
        result1 = admin_dex.get_protocol_vault_address()
        result2 = admin_dex.get_protocol_vault_address()
        assert str(result1) == str(result2)


# ===========================================================================
# Tests for initialize (async)
# ===========================================================================


class TestInitialize:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        result = await admin_dex.initialize(
            collateral_token_addr=TEST_COLLATERAL_ADDR,
            backstop_liquidator_addr=TEST_BACKSTOP_ADDR,
        )

        admin_dex._send_tx.assert_awaited_once()
        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::initialize"
        assert payload.type_arguments == []
        assert payload.function_arguments == [TEST_COLLATERAL_ADDR, TEST_BACKSTOP_ADDR]
        assert result == _make_tx_response()

    async def test_returns_tx_response(self, admin_dex: DecibelAdminDex) -> None:
        custom_response = {"hash": "0xcafe", "success": True}
        admin_dex._send_tx.return_value = custom_response

        result = await admin_dex.initialize(
            collateral_token_addr=TEST_COLLATERAL_ADDR,
            backstop_liquidator_addr=TEST_BACKSTOP_ADDR,
        )
        assert result == custom_response


# ===========================================================================
# Tests for initialize_protocol_vault (async)
# ===========================================================================


class TestInitializeProtocolVault:
    async def test_sends_create_and_fund_vault(self, admin_dex: DecibelAdminDex) -> None:
        with patch(
            "decibel.admin.BaseSDK.get_primary_subaccount_address",
            return_value=TEST_ACCOUNT_ADDR,
        ):
            await admin_dex.initialize_protocol_vault(
                collateral_token_addr=TEST_COLLATERAL_ADDR,
                initial_funding=500_000,
            )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_api::create_and_fund_vault"

    async def test_sets_correct_vault_name(self, admin_dex: DecibelAdminDex) -> None:
        with patch(
            "decibel.admin.BaseSDK.get_primary_subaccount_address",
            return_value=TEST_ACCOUNT_ADDR,
        ):
            await admin_dex.initialize_protocol_vault(
                collateral_token_addr=TEST_COLLATERAL_ADDR,
                initial_funding=0,
            )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        args = payload.function_arguments
        # args[0] = subaccount_addr, args[1] = collateral, args[2] = vault_name
        assert args[2] == "Decibel Protocol Vault"
        assert args[5] == "DPV"  # vault_share_symbol
        assert args[12] is True  # accepts_contributions
        assert args[13] is False  # delegate_to_creator

    async def test_passes_initial_funding(self, admin_dex: DecibelAdminDex) -> None:
        with patch(
            "decibel.admin.BaseSDK.get_primary_subaccount_address",
            return_value=TEST_ACCOUNT_ADDR,
        ):
            await admin_dex.initialize_protocol_vault(
                collateral_token_addr=TEST_COLLATERAL_ADDR,
                initial_funding=999_999,
            )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[11] == 999_999


# ===========================================================================
# Tests for delegate_protocol_vault_trading_to (async)
# ===========================================================================


class TestDelegateProtocolVaultTradingTo:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.delegate_protocol_vault_trading_to(
            vault_address=TEST_VAULT_ADDR,
            account_to_delegate_to=TEST_DELEGATE_ADDR,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_admin_api::delegate_dex_actions_to"
        assert payload.function_arguments == [TEST_VAULT_ADDR, TEST_DELEGATE_ADDR, None]


# ===========================================================================
# Tests for update_vault_use_global_redemption_slippage_adjustment (async)
# ===========================================================================


class TestUpdateVaultRedemptionSlippage:
    async def test_sends_correct_function_true(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.update_vault_use_global_redemption_slippage_adjustment(
            vault_address=TEST_VAULT_ADDR,
            use_global_redemption_slippage_adjustment=True,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::vault_admin_api"
            "::update_vault_use_global_redemption_slippage_adjustment"
        )
        assert payload.function_arguments == [TEST_VAULT_ADDR, True]

    async def test_sends_correct_function_false(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.update_vault_use_global_redemption_slippage_adjustment(
            vault_address=TEST_VAULT_ADDR,
            use_global_redemption_slippage_adjustment=False,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function_arguments == [TEST_VAULT_ADDR, False]


# ===========================================================================
# Tests for authorize_oracle_and_mark_update (async)
# ===========================================================================


class TestAuthorizeOracleAndMarkUpdate:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        oracle_updater = "0x" + "11" * 32
        await admin_dex.authorize_oracle_and_mark_update(oracle_updater)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::admin_apis::add_oracle_and_mark_update_permission"
        )
        assert payload.function_arguments == [oracle_updater]


# ===========================================================================
# Tests for add_access_control_admin (async)
# ===========================================================================


class TestAddAccessControlAdmin:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        delegated = "0x" + "11" * 32
        await admin_dex.add_access_control_admin(delegated)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::add_access_control_admin"
        assert payload.function_arguments == [delegated]


# ===========================================================================
# Tests for add_market_list_admin (async)
# ===========================================================================


class TestAddMarketListAdmin:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        delegated = "0x" + "22" * 32
        await admin_dex.add_market_list_admin(delegated)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::add_market_list_admin"
        assert payload.function_arguments == [delegated]


# ===========================================================================
# Tests for add_market_risk_governor (async)
# ===========================================================================


class TestAddMarketRiskGovernor:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        delegated = "0x" + "33" * 32
        await admin_dex.add_market_risk_governor(delegated)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::add_market_risk_governor"
        assert payload.function_arguments == [delegated]


# ===========================================================================
# Tests for register_market_with_internal_oracle (async)
# ===========================================================================


class TestRegisterMarketWithInternalOracle:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.register_market_with_internal_oracle(
            name="BTC-USD",
            sz_decimals=3,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=1_000_000,
            max_leverage=20,
            margin_call_fee_pct=500,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::admin_apis::register_market_with_internal_oracle"
        )
        args = payload.function_arguments
        assert args[0] == "BTC-USD"
        assert args[1] == 3
        assert args[2] == 1  # min_size
        assert args[6] == 20  # max_leverage
        assert args[7] == 500  # margin_call_fee_pct
        assert args[8] is True  # taker_in_next_block default
        assert args[9] == 1  # initial_oracle_price default
        assert args[10] == 60  # max_staleness_secs default

    async def test_custom_defaults_overridden(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.register_market_with_internal_oracle(
            name="ETH-USD",
            sz_decimals=4,
            min_size=10,
            lot_size=5,
            ticker_size=2,
            max_open_interest=5_000_000,
            max_leverage=50,
            margin_call_fee_pct=200,
            taker_in_next_block=False,
            initial_oracle_price=3000,
            max_staleness_secs=120,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        args = payload.function_arguments
        assert args[8] is False
        assert args[9] == 3000
        assert args[10] == 120


# ===========================================================================
# Tests for register_market_with_pyth_oracle (async)
# ===========================================================================


class TestRegisterMarketWithPythOracle:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        pyth_bytes = list(range(32))
        await admin_dex.register_market_with_pyth_oracle(
            name="SOL-USD",
            sz_decimals=2,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=1_000_000,
            max_leverage=10,
            margin_call_fee_pct=500,
            pyth_identifier_bytes=pyth_bytes,
            pyth_max_staleness_secs=30,
            pyth_confidence_interval_threshold=100,
            pyth_decimals=8,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::register_market_with_pyth_oracle"
        args = payload.function_arguments
        assert args[0] == "SOL-USD"
        assert args[8] is True  # taker_in_next_block default
        assert args[9] == pyth_bytes
        assert args[10] == 30
        assert args[11] == 100
        assert args[12] == 8


# ===========================================================================
# Tests for register_market_with_composite_oracle_primary_pyth (async)
# ===========================================================================


class TestRegisterMarketWithCompositePyth:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        pyth_bytes = list(range(32))
        await admin_dex.register_market_with_composite_oracle_primary_pyth(
            name="AVAX-USD",
            sz_decimals=2,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=500_000,
            max_leverage=10,
            margin_call_fee_pct=300,
            pyth_identifier_bytes=pyth_bytes,
            pyth_max_staleness_secs=30,
            pyth_confidence_interval_threshold=200,
            pyth_decimals=8,
            internal_initial_price=25,
            internal_max_staleness_secs=60,
            oracles_deviation_bps=100,
            consecutive_deviation_count=3,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::admin_apis::register_market_with_composite_oracle_primary_pyth"
        )
        args = payload.function_arguments
        # 0=name, 1=sz_dec, 2=min_size, 3=lot, 4=ticker, 5=max_oi, 6=max_lev, 7=margin,
        # 8=taker_in_next_block, 9=pyth_bytes, 10=pyth_staleness, 11=pyth_ci, 12=pyth_dec,
        # 13=internal_initial_price, 14=internal_max_staleness, 15=oracles_dev_bps, 16=dev_count
        assert args[0] == "AVAX-USD"
        assert args[13] == 25  # internal_initial_price
        assert args[14] == 60  # internal_max_staleness_secs
        assert args[15] == 100  # oracles_deviation_bps
        assert args[16] == 3  # consecutive_deviation_count


# ===========================================================================
# Tests for register_market_with_composite_oracle_primary_chainlink (async)
# ===========================================================================


class TestRegisterMarketWithCompositeChainlink:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        chainlink_bytes = list(range(32))
        await admin_dex.register_market_with_composite_oracle_primary_chainlink(
            name="BNB-USD",
            sz_decimals=2,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=300_000,
            max_leverage=10,
            margin_call_fee_pct=300,
            rescale_decimals=8,
            chainlink_feed_id_bytes=chainlink_bytes,
            chainlink_max_staleness_secs=30,
            internal_max_staleness_secs=60,
            internal_initial_price=250,
            oracles_deviation_bps=50,
            consecutive_deviation_count=5,
        )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::admin_apis"
            "::register_market_with_composite_oracle_primary_chainlink"
        )
        args = payload.function_arguments
        assert args[0] == "BNB-USD"
        assert args[9] == chainlink_bytes
        assert args[11] == 8  # rescale_decimals
        assert args[12] == 250  # internal_initial_price


# ===========================================================================
# Tests for update_internal_oracle_price (async)
# ===========================================================================


class TestUpdateInternalOraclePrice:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR):
            await admin_dex.update_internal_oracle_price(
                market_name=TEST_MARKET_NAME, oracle_price=3000
            )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::update_mark_for_internal_oracle"
        assert payload.function_arguments == [TEST_MARKET_ADDR, 3000, [], [], True]

    async def test_resolves_market_addr(self, admin_dex: DecibelAdminDex) -> None:
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR) as mock_get_addr:
            await admin_dex.update_internal_oracle_price(market_name="SOL-USD", oracle_price=100)

        mock_get_addr.assert_called_once_with(
            "SOL-USD", admin_dex._config.deployment.perp_engine_global
        )


# ===========================================================================
# Tests for update_pyth_oracle_price (async)
# ===========================================================================


class TestUpdatePythOraclePrice:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        vaa = [1, 2, 3, 4]
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR):
            await admin_dex.update_pyth_oracle_price(market_name=TEST_MARKET_NAME, vaa=vaa)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::update_mark_for_pyth_oracle"
        assert payload.function_arguments == [TEST_MARKET_ADDR, vaa, [], [], True]


# ===========================================================================
# Tests for set_market_adl_trigger_threshold (async)
# ===========================================================================


class TestSetMarketAdlTriggerThreshold:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR):
            await admin_dex.set_market_adl_trigger_threshold(
                market_name=TEST_MARKET_NAME, threshold=500
            )

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::set_market_adl_trigger_threshold"
        assert payload.function_arguments == [TEST_MARKET_ADDR, 500]


# ===========================================================================
# Tests for update_price_to_pyth_only (async)
# ===========================================================================


class TestUpdatePriceToPythOnly:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        vaas = [[1, 2], [3, 4]]
        await admin_dex.update_price_to_pyth_only(vaas=vaas)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::pyth::update_price_feeds_with_funder"
        assert payload.function_arguments == [vaas]


# ===========================================================================
# Tests for update_price_to_chainlink_only (async)
# ===========================================================================


class TestUpdatePriceToChainlinkOnly:
    async def test_sends_correct_function(self, admin_dex: DecibelAdminDex) -> None:
        signed_report = [1, 2, 3, 4, 5]
        await admin_dex.update_price_to_chainlink_only(signed_report=signed_report)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::chainlink_state::verify_and_store_single_price"
        assert payload.function_arguments == [signed_report]


# ===========================================================================
# Tests for mint_usdc (async)
# ===========================================================================


class TestMintUsdc:
    async def test_sends_correct_function_with_str_addr(self, admin_dex: DecibelAdminDex) -> None:
        to_addr = "0x" + "11" * 32
        await admin_dex.mint_usdc(to_addr=to_addr, amount=1_000_000)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::usdc::mint"
        assert payload.function_arguments == [to_addr, 1_000_000]

    async def test_sends_correct_function_with_account_address(
        self, admin_dex: DecibelAdminDex
    ) -> None:
        addr = AccountAddress.from_str("0x" + "11" * 32)
        await admin_dex.mint_usdc(to_addr=addr, amount=500_000)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        # AccountAddress should be converted to str
        assert isinstance(payload.function_arguments[0], str)
        assert payload.function_arguments[1] == 500_000

    async def test_converts_account_address_to_str(self, admin_dex: DecibelAdminDex) -> None:
        addr = AccountAddress.from_str("0x" + "22" * 32)
        await admin_dex.mint_usdc(to_addr=addr, amount=100)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function_arguments[0] == str(addr)


# ===========================================================================
# Tests for set_public_minting (async)
# ===========================================================================


class TestSetPublicMinting:
    async def test_allows_minting(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.set_public_minting(allow=True)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::usdc::set_public_minting"
        assert payload.function_arguments == [True]

    async def test_disallows_minting(self, admin_dex: DecibelAdminDex) -> None:
        await admin_dex.set_public_minting(allow=False)

        payload: InputEntryFunctionData = admin_dex._send_tx.call_args.args[0]
        assert payload.function_arguments == [False]


# ===========================================================================
# Tests for usdc_balance (async)
# ===========================================================================


class TestUsdcBalance:
    async def test_returns_balance_for_str_addr(self, admin_dex: DecibelAdminDex) -> None:
        admin_dex._aptos.view = AsyncMock(return_value=["1000000"])
        result = await admin_dex.usdc_balance(addr="0x" + "11" * 32)
        assert result == 1_000_000

    async def test_returns_balance_for_account_address(self, admin_dex: DecibelAdminDex) -> None:
        admin_dex._aptos.view = AsyncMock(return_value=["500000"])
        addr = AccountAddress.from_str("0x" + "11" * 32)
        result = await admin_dex.usdc_balance(addr=addr)
        assert result == 500_000

    async def test_converts_account_address_to_str(self, admin_dex: DecibelAdminDex) -> None:
        addr = AccountAddress.from_str("0x" + "33" * 32)
        admin_dex._aptos.view = AsyncMock(return_value=["0"])
        await admin_dex.usdc_balance(addr=addr)

        call_args = admin_dex._aptos.view.call_args
        # Third argument should be a list with addr string and usdc address
        assert str(addr) in call_args.args[2]


# ===========================================================================
# Tests for DecibelAdminDexSync.__init__
# ===========================================================================


class TestDecibelAdminDexSyncInit:
    def test_init_calls_super(self, test_config, mock_account) -> None:
        with patch("decibel.admin.BaseSDKSync.__init__") as mock_super:
            mock_super.return_value = None
            dex = DecibelAdminDexSync.__new__(DecibelAdminDexSync)
            DecibelAdminDexSync.__init__(dex, test_config, mock_account)
            mock_super.assert_called_once_with(test_config, mock_account, None)


# ===========================================================================
# Tests for DecibelAdminDexSync.get_protocol_vault_address
# ===========================================================================


class TestDecibelAdminDexSyncGetProtocolVaultAddress:
    def test_returns_account_address(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        result = admin_dex_sync.get_protocol_vault_address()
        assert isinstance(result, AccountAddress)

    def test_is_deterministic(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        result1 = admin_dex_sync.get_protocol_vault_address()
        result2 = admin_dex_sync.get_protocol_vault_address()
        assert str(result1) == str(result2)

    def test_matches_async_version(
        self, admin_dex: DecibelAdminDex, admin_dex_sync: DecibelAdminDexSync
    ) -> None:
        async_result = admin_dex.get_protocol_vault_address()
        sync_result = admin_dex_sync.get_protocol_vault_address()
        assert str(async_result) == str(sync_result)


# ===========================================================================
# Tests for DecibelAdminDexSync.initialize
# ===========================================================================


class TestDecibelAdminDexSyncInitialize:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        result = admin_dex_sync.initialize(
            collateral_token_addr=TEST_COLLATERAL_ADDR,
            backstop_liquidator_addr=TEST_BACKSTOP_ADDR,
        )

        admin_dex_sync._send_tx.assert_called_once()
        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::initialize"
        assert payload.function_arguments == [TEST_COLLATERAL_ADDR, TEST_BACKSTOP_ADDR]
        assert result == _make_tx_response()


# ===========================================================================
# Tests for DecibelAdminDexSync.initialize_protocol_vault
# ===========================================================================


class TestDecibelAdminDexSyncInitializeProtocolVault:
    def test_sends_create_and_fund_vault(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        with patch(
            "decibel.admin.BaseSDKSync.get_primary_subaccount_address",
            return_value=TEST_ACCOUNT_ADDR,
        ):
            admin_dex_sync.initialize_protocol_vault(
                collateral_token_addr=TEST_COLLATERAL_ADDR,
                initial_funding=1_000_000,
            )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_api::create_and_fund_vault"
        assert payload.function_arguments[11] == 1_000_000  # initial_funding


# ===========================================================================
# Tests for DecibelAdminDexSync.delegate_protocol_vault_trading_to
# ===========================================================================


class TestDecibelAdminDexSyncDelegateProtocolVaultTradingTo:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        admin_dex_sync.delegate_protocol_vault_trading_to(
            vault_address=TEST_VAULT_ADDR,
            account_to_delegate_to=TEST_DELEGATE_ADDR,
        )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::vault_admin_api::delegate_dex_actions_to"
        assert payload.function_arguments == [TEST_VAULT_ADDR, TEST_DELEGATE_ADDR, None]


# ===========================================================================
# Tests for DecibelAdminDexSync.update_vault_use_global_redemption_slippage_adjustment
# ===========================================================================


class TestDecibelAdminDexSyncUpdateVaultRedemptionSlippage:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        admin_dex_sync.update_vault_use_global_redemption_slippage_adjustment(
            vault_address=TEST_VAULT_ADDR,
            use_global_redemption_slippage_adjustment=True,
        )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::vault_admin_api"
            "::update_vault_use_global_redemption_slippage_adjustment"
        )
        assert payload.function_arguments == [TEST_VAULT_ADDR, True]


# ===========================================================================
# Tests for DecibelAdminDexSync.authorize_oracle_and_mark_update
# ===========================================================================


class TestDecibelAdminDexSyncAuthorizeOracle:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        oracle_updater = "0x" + "11" * 32
        admin_dex_sync.authorize_oracle_and_mark_update(oracle_updater)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::admin_apis::add_oracle_and_mark_update_permission"
        )
        assert payload.function_arguments == [oracle_updater]


# ===========================================================================
# Tests for DecibelAdminDexSync.add_access_control_admin
# ===========================================================================


class TestDecibelAdminDexSyncAddAccessControlAdmin:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        delegated = "0x" + "22" * 32
        admin_dex_sync.add_access_control_admin(delegated)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::add_access_control_admin"
        assert payload.function_arguments == [delegated]


# ===========================================================================
# Tests for DecibelAdminDexSync.add_market_list_admin
# ===========================================================================


class TestDecibelAdminDexSyncAddMarketListAdmin:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        delegated = "0x" + "33" * 32
        admin_dex_sync.add_market_list_admin(delegated)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::add_market_list_admin"


# ===========================================================================
# Tests for DecibelAdminDexSync.add_market_risk_governor
# ===========================================================================


class TestDecibelAdminDexSyncAddMarketRiskGovernor:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        delegated = "0x" + "44" * 32
        admin_dex_sync.add_market_risk_governor(delegated)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::add_market_risk_governor"


# ===========================================================================
# Tests for DecibelAdminDexSync.register_market_with_internal_oracle
# ===========================================================================


class TestDecibelAdminDexSyncRegisterMarketInternal:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        admin_dex_sync.register_market_with_internal_oracle(
            name="BTC-USD",
            sz_decimals=3,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=1_000_000,
            max_leverage=20,
            margin_call_fee_pct=500,
        )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::admin_apis::register_market_with_internal_oracle"
        )
        assert payload.function_arguments[0] == "BTC-USD"
        assert payload.function_arguments[8] is True  # taker_in_next_block default


# ===========================================================================
# Tests for DecibelAdminDexSync.register_market_with_pyth_oracle
# ===========================================================================


class TestDecibelAdminDexSyncRegisterMarketPyth:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        pyth_bytes = list(range(32))
        admin_dex_sync.register_market_with_pyth_oracle(
            name="ETH-USD",
            sz_decimals=4,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=2_000_000,
            max_leverage=15,
            margin_call_fee_pct=400,
            pyth_identifier_bytes=pyth_bytes,
            pyth_max_staleness_secs=45,
            pyth_confidence_interval_threshold=150,
            pyth_decimals=8,
            taker_in_next_block=False,
        )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::register_market_with_pyth_oracle"
        assert payload.function_arguments[8] is False  # taker_in_next_block


# ===========================================================================
# Tests for DecibelAdminDexSync.register_market_with_composite_oracle_primary_pyth
# ===========================================================================


class TestDecibelAdminDexSyncRegisterMarketCompositePyth:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        pyth_bytes = list(range(32))
        admin_dex_sync.register_market_with_composite_oracle_primary_pyth(
            name="ARB-USD",
            sz_decimals=2,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=300_000,
            max_leverage=10,
            margin_call_fee_pct=250,
            pyth_identifier_bytes=pyth_bytes,
            pyth_max_staleness_secs=30,
            pyth_confidence_interval_threshold=100,
            pyth_decimals=8,
            internal_initial_price=1,
            internal_max_staleness_secs=60,
            oracles_deviation_bps=50,
            consecutive_deviation_count=2,
        )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function
            == f"{TEST_PACKAGE}::admin_apis::register_market_with_composite_oracle_primary_pyth"
        )


# ===========================================================================
# Tests for DecibelAdminDexSync.register_market_with_composite_oracle_primary_chainlink
# ===========================================================================


class TestDecibelAdminDexSyncRegisterMarketCompositeChainlink:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        chainlink_bytes = list(range(32))
        admin_dex_sync.register_market_with_composite_oracle_primary_chainlink(
            name="LINK-USD",
            sz_decimals=2,
            min_size=1,
            lot_size=1,
            ticker_size=1,
            max_open_interest=200_000,
            max_leverage=10,
            margin_call_fee_pct=300,
            rescale_decimals=8,
            chainlink_feed_id_bytes=chainlink_bytes,
            chainlink_max_staleness_secs=30,
            internal_max_staleness_secs=60,
            internal_initial_price=15,
            oracles_deviation_bps=75,
            consecutive_deviation_count=4,
        )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert (
            payload.function == f"{TEST_PACKAGE}::admin_apis"
            "::register_market_with_composite_oracle_primary_chainlink"
        )
        assert payload.function_arguments[11] == 8  # rescale_decimals


# ===========================================================================
# Tests for DecibelAdminDexSync.update_internal_oracle_price
# ===========================================================================


class TestDecibelAdminDexSyncUpdateInternalOraclePrice:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR):
            admin_dex_sync.update_internal_oracle_price(
                market_name=TEST_MARKET_NAME, oracle_price=2500
            )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::update_mark_for_internal_oracle"
        assert payload.function_arguments == [TEST_MARKET_ADDR, 2500, [], [], True]


# ===========================================================================
# Tests for DecibelAdminDexSync.update_pyth_oracle_price
# ===========================================================================


class TestDecibelAdminDexSyncUpdatePythOraclePrice:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        vaa = [10, 20, 30]
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR):
            admin_dex_sync.update_pyth_oracle_price(market_name=TEST_MARKET_NAME, vaa=vaa)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::update_mark_for_pyth_oracle"
        assert payload.function_arguments == [TEST_MARKET_ADDR, vaa, [], [], True]


# ===========================================================================
# Tests for DecibelAdminDexSync.set_market_adl_trigger_threshold
# ===========================================================================


class TestDecibelAdminDexSyncSetMarketAdlTriggerThreshold:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        with patch("decibel.admin.get_market_addr", return_value=TEST_MARKET_ADDR):
            admin_dex_sync.set_market_adl_trigger_threshold(
                market_name=TEST_MARKET_NAME, threshold=750
            )

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::admin_apis::set_market_adl_trigger_threshold"
        assert payload.function_arguments == [TEST_MARKET_ADDR, 750]


# ===========================================================================
# Tests for DecibelAdminDexSync.update_price_to_pyth_only
# ===========================================================================


class TestDecibelAdminDexSyncUpdatePricePythOnly:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        vaas = [[1, 2], [3, 4]]
        admin_dex_sync.update_price_to_pyth_only(vaas=vaas)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::pyth::update_price_feeds_with_funder"
        assert payload.function_arguments == [vaas]


# ===========================================================================
# Tests for DecibelAdminDexSync.update_price_to_chainlink_only
# ===========================================================================


class TestDecibelAdminDexSyncUpdatePriceChainlinkOnly:
    def test_sends_correct_function(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        signed_report = [5, 10, 15]
        admin_dex_sync.update_price_to_chainlink_only(signed_report=signed_report)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::chainlink_state::verify_and_store_single_price"
        assert payload.function_arguments == [signed_report]


# ===========================================================================
# Tests for DecibelAdminDexSync.mint_usdc
# ===========================================================================


class TestDecibelAdminDexSyncMintUsdc:
    def test_sends_correct_function_with_str(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        to_addr = "0x" + "11" * 32
        admin_dex_sync.mint_usdc(to_addr=to_addr, amount=2_000_000)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::usdc::mint"
        assert payload.function_arguments == [to_addr, 2_000_000]

    def test_sends_correct_function_with_account_address(
        self, admin_dex_sync: DecibelAdminDexSync
    ) -> None:
        addr = AccountAddress.from_str("0x" + "55" * 32)
        admin_dex_sync.mint_usdc(to_addr=addr, amount=300_000)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments[0] == str(addr)
        assert payload.function_arguments[1] == 300_000


# ===========================================================================
# Tests for DecibelAdminDexSync.set_public_minting
# ===========================================================================


class TestDecibelAdminDexSyncSetPublicMinting:
    def test_allows_minting(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        admin_dex_sync.set_public_minting(allow=True)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function == f"{TEST_PACKAGE}::usdc::set_public_minting"
        assert payload.function_arguments == [True]

    def test_disallows_minting(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        admin_dex_sync.set_public_minting(allow=False)

        payload: InputEntryFunctionData = admin_dex_sync._send_tx.call_args.args[0]
        assert payload.function_arguments == [False]


# ===========================================================================
# Tests for DecibelAdminDexSync.usdc_balance
# ===========================================================================


class TestDecibelAdminDexSyncUsdcBalance:
    def test_returns_balance_for_str_addr(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = ["2000000"]
        admin_dex_sync._http_client.post.return_value = mock_response

        result = admin_dex_sync.usdc_balance(addr="0x" + "11" * 32)
        assert result == 2_000_000

    def test_returns_balance_for_account_address(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        addr = AccountAddress.from_str("0x" + "22" * 32)
        mock_response = MagicMock()
        mock_response.json.return_value = ["750000"]
        admin_dex_sync._http_client.post.return_value = mock_response

        result = admin_dex_sync.usdc_balance(addr=addr)
        assert result == 750_000

    def test_uses_http_client_when_available(self, admin_dex_sync: DecibelAdminDexSync) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = ["100"]
        admin_dex_sync._http_client.post.return_value = mock_response

        admin_dex_sync.usdc_balance(addr="0x" + "11" * 32)
        admin_dex_sync._http_client.post.assert_called_once()
