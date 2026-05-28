"""Integration tests for the write SDK against live Decibel testnet.

These tests exercise the full transaction lifecycle:
  build -> simulate -> sign -> submit -> confirm

Requires two env vars:
    DECIBEL_API_KEY      - API key for testnet
    DECIBEL_PRIVATE_KEY  - Private key of a funded testnet account

Run with:
    DECIBEL_API_KEY=<key> DECIBEL_PRIVATE_KEY=<key> \
        uv run pytest tests/api_resources/test_testnet_write_integration.py -v

The account MUST have:
    - Testnet APT for gas
    - Testnet USDC (minted via restricted_mint)
    - An existing subaccount with deposited USDC
"""

from __future__ import annotations

import asyncio
import os

import pytest

from decibel._constants import TESTNET_CONFIG
from decibel._exceptions import TxnConfirmError

# ---------------------------------------------------------------------------
# Skip if credentials not available
# ---------------------------------------------------------------------------

DECIBEL_API_KEY = os.environ.get("DECIBEL_API_KEY")
DECIBEL_PRIVATE_KEY = os.environ.get("DECIBEL_PRIVATE_KEY")

pytestmark = pytest.mark.skipif(
    not DECIBEL_API_KEY or not DECIBEL_PRIVATE_KEY,
    reason="DECIBEL_API_KEY and DECIBEL_PRIVATE_KEY env vars required",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def account():
    from aptos_sdk.account import Account
    from aptos_sdk.ed25519 import PrivateKey

    return Account.load_key(PrivateKey.from_hex(DECIBEL_PRIVATE_KEY).hex())


@pytest.fixture(scope="module")
def write_client(account):
    from decibel import BaseSDKOptions, DecibelWriteDex

    return DecibelWriteDex(
        TESTNET_CONFIG,
        account,
        opts=BaseSDKOptions(
            node_api_key=DECIBEL_API_KEY,
            skip_simulate=False,
            no_fee_payer=True,
            time_delta_ms=0,
        ),
    )


@pytest.fixture(scope="module")
def read_client():
    from decibel.read import DecibelReadDex

    return DecibelReadDex(TESTNET_CONFIG, api_key=DECIBEL_API_KEY)


@pytest.fixture(scope="module")
def subaccount_addr(account):
    """Get the primary subaccount address."""
    from decibel._utils import get_primary_subaccount_addr

    return get_primary_subaccount_addr(
        str(account.address()),
        TESTNET_CONFIG.compat_version,
        TESTNET_CONFIG.deployment.package,
    )


@pytest.fixture(scope="module")
def eth_market(read_client):
    """Get ETH market info for order tests."""
    markets = asyncio.run(read_client.markets.get_all())
    eth = next((m for m in markets if "ETH" in m.market_name), None)
    if eth is None:
        pytest.skip("No ETH market found on testnet")
    return eth


# ---------------------------------------------------------------------------
# Mint USDC
# ---------------------------------------------------------------------------


class TestMintUSDC:
    """Test minting testnet USDC via restricted_mint."""

    async def test_restricted_mint(self, write_client) -> None:
        """SHALL mint testnet USDC (or skip if daily limit reached)."""
        from decibel._transaction_builder import InputEntryFunctionData
        from decibel._utils import amount_to_chain_units

        payload = InputEntryFunctionData(
            function=f"{TESTNET_CONFIG.deployment.package}::usdc::restricted_mint",
            function_arguments=[amount_to_chain_units(100.0)],
        )
        try:
            result = await write_client._send_tx(payload)
            assert result.get("vm_status") == "Executed successfully"
            assert "hash" in result
        except TxnConfirmError as e:
            if "MINT_ACCOUNT_LIMIT_EXCEEDED" in str(e):
                pytest.skip("Daily mint limit exceeded")
            raise


# ---------------------------------------------------------------------------
# Subaccount management
# ---------------------------------------------------------------------------


class TestSubaccountManagement:
    """Test subaccount creation and querying."""

    async def test_subaccount_exists(self, read_client, account) -> None:
        """Account SHALL have at least one subaccount after setup."""
        subs = await read_client.user_subaccounts.get_by_addr(owner_addr=str(account.address()))
        assert len(subs) >= 1
        assert subs[0].subaccount_address.startswith("0x")

    async def test_primary_subaccount_address_matches(
        self, read_client, account, subaccount_addr
    ) -> None:
        """Computed primary subaccount address SHALL match on-chain."""
        subs = await read_client.user_subaccounts.get_by_addr(owner_addr=str(account.address()))
        sub_addrs = [s.subaccount_address for s in subs]
        assert subaccount_addr in sub_addrs


# ---------------------------------------------------------------------------
# Deposit / Withdraw
# ---------------------------------------------------------------------------


class TestDepositWithdraw:
    """Test deposit and withdrawal flows."""

    async def test_deposit(self, write_client) -> None:
        """SHALL deposit USDC into the primary subaccount."""
        from decibel._utils import amount_to_chain_units

        result = await write_client.deposit(amount_to_chain_units(50.0))
        assert result.get("vm_status") == "Executed successfully"
        assert "hash" in result

    async def test_account_overview_after_deposit(self, read_client, subaccount_addr) -> None:
        """Account overview SHALL reflect deposited funds."""
        overview = await read_client.account_overview.get_by_addr(sub_addr=subaccount_addr)
        assert overview.perp_equity_balance >= 0
        assert overview.total_margin >= 0

    async def test_withdraw(self, write_client) -> None:
        """SHALL withdraw a small amount of USDC."""
        from decibel._utils import amount_to_chain_units

        result = await write_client.withdraw(amount_to_chain_units(10.0))
        assert result.get("vm_status") == "Executed successfully"
        assert "hash" in result


# ---------------------------------------------------------------------------
# Order lifecycle: place -> query -> cancel
# ---------------------------------------------------------------------------


class TestOrderLifecycle:
    """Test the full order lifecycle: place, query, cancel."""

    async def test_place_limit_order(self, write_client, eth_market) -> None:
        """SHALL place a limit buy order far below market price."""
        from decibel import PlaceOrderSuccess, TimeInForce
        from decibel._utils import amount_to_chain_units

        low_price = amount_to_chain_units(500.0, eth_market.px_decimals)
        size = int(eth_market.min_size)

        result = await write_client.place_order(
            market_name=eth_market.market_name,
            price=low_price,
            size=size,
            is_buy=True,
            time_in_force=TimeInForce.GoodTillCanceled,
            is_reduce_only=False,
            client_order_id="test-integ-limit-001",
            tick_size=int(eth_market.tick_size),
        )

        assert isinstance(result, PlaceOrderSuccess)
        assert result.transaction_hash.startswith("0x")

    async def test_query_open_orders(self, read_client, subaccount_addr) -> None:
        """SHALL query open orders without error."""
        result = await read_client.user_open_orders.get_by_addr(sub_addr=subaccount_addr)
        assert result.total_count >= 0

    async def test_cancel_all_open_orders(
        self, write_client, read_client, eth_market, subaccount_addr
    ) -> None:
        """SHALL cancel any remaining open orders for cleanup."""
        result = await read_client.user_open_orders.get_by_addr(sub_addr=subaccount_addr)

        for order in result.items:
            if order.market == eth_market.market_addr:
                try:
                    cancel_tx = await write_client.cancel_order(
                        market_name=eth_market.market_name,
                        order_id=int(order.order_id),
                    )
                    vm = cancel_tx.get("vm_status")
                    assert vm == "Executed successfully"
                except (TxnConfirmError, ValueError):
                    pass  # Order may have already been cancelled


# ---------------------------------------------------------------------------
# Read endpoints that require a funded account
# ---------------------------------------------------------------------------


class TestAuthenticatedReadEndpoints:
    """Test read endpoints that need a real account."""

    async def test_user_positions(self, read_client, subaccount_addr) -> None:
        """SHALL return positions list (may be empty)."""
        positions = await read_client.user_positions.get_by_addr(sub_addr=subaccount_addr)
        assert isinstance(positions, list)

    async def test_user_order_history(self, read_client, subaccount_addr) -> None:
        """SHALL return order history."""
        result = await read_client.user_order_history.get_by_addr(sub_addr=subaccount_addr)
        assert isinstance(result.items, list)

    async def test_user_trade_history(self, read_client, subaccount_addr) -> None:
        """SHALL return trade history."""
        result = await read_client.user_trade_history.get_by_addr(sub_addr=subaccount_addr)
        assert isinstance(result.items, list)

    async def test_user_active_twaps(self, read_client, subaccount_addr) -> None:
        """SHALL return active TWAPs (likely empty)."""
        twaps = await read_client.user_active_twaps.get_by_addr(sub_addr=subaccount_addr)
        assert isinstance(twaps, list)

    async def test_user_fund_history(self, read_client, subaccount_addr) -> None:
        """SHALL return fund history (deposits/withdrawals)."""
        result = await read_client.user_fund_history.get_by_addr(sub_addr=subaccount_addr)
        assert isinstance(result.funds, list)
        assert result.total >= 1

    async def test_user_subaccounts(self, read_client, account) -> None:
        """SHALL return subaccount list."""
        subs = await read_client.user_subaccounts.get_by_addr(owner_addr=str(account.address()))
        assert len(subs) >= 1
        assert subs[0].subaccount_address.startswith("0x")

    async def test_delegations(self, read_client, subaccount_addr) -> None:
        """SHALL return delegations (may be empty)."""
        delegations = await read_client.delegations.get_all(sub_addr=subaccount_addr)
        assert isinstance(delegations, list)
