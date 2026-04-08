"""
Buy-Low-Sell-High Bot — Decibel Python SDK Example
====================================================

A simple trading bot that:
  1. Connects to the Decibel exchange via WebSocket for real-time prices
  2. Places a limit BUY order at a configured spread below the oracle price
  3. Monitors for fills via WebSocket order updates
  4. When the buy fills, places a limit SELL order at a spread above entry
  5. When the sell fills, starts over

This is an EXAMPLE for educational purposes — NOT production trading software.
It demonstrates the full SDK surface: read (REST + WebSocket) and write (on-chain).

Setup
-----

1. Create and fund an Aptos testnet account with APT (for gas) and USDC:

       # Generate account
       python -c "
       from aptos_sdk.account import Account
       a = Account.generate()
       print(f'Address: {a.address()}')
       print(f'Private key: {a.private_key.hex()}')
       "

       # Fund with APT via testnet faucet, then mint USDC:
       PRIVATE_KEY=0x... APTOS_NODE_API_KEY=... python -c "
       import asyncio
       from aptos_sdk.account import Account
       from aptos_sdk.ed25519 import PrivateKey
       from decibel import TESTNET_CONFIG, BaseSDKOptions, DecibelWriteDex, amount_to_chain_units
       from decibel._transaction_builder import InputEntryFunctionData

       async def main():
           acct = Account.load_key(PrivateKey.from_hex('$PRIVATE_KEY').hex())
           w = DecibelWriteDex(TESTNET_CONFIG, acct, opts=BaseSDKOptions(
               node_api_key='$APTOS_NODE_API_KEY', no_fee_payer=True))

           # Create subaccount
           await w.create_subaccount()

           # Mint USDC
           await w._send_tx(InputEntryFunctionData(
               function=f'{TESTNET_CONFIG.deployment.package}::usdc::restricted_mint',
               function_arguments=[amount_to_chain_units(1000.0)]))

           # Deposit
           await w.deposit(amount_to_chain_units(500.0))

       asyncio.run(main())
       "

2. Set environment variables:

       export PRIVATE_KEY="0x..."
       export APTOS_NODE_API_KEY="aptoslabs_..."

       # Optional — override defaults:
       export MARKET="ETH/USD"          # default: ETH/USD
       export BUY_SPREAD_PCT="1.0"      # default: 1.0 (buy 1% below oracle)
       export SELL_SPREAD_PCT="1.0"     # default: 1.0 (sell 1% above entry)
       export ORDER_SIZE_USD="100"      # default: 100 (notional size in USD)
       export NETWORK="testnet"         # default: testnet

3. Run:

       uv run python examples/buy_low_sell_high_bot.py

Architecture
------------

    ┌─────────────────────────────────────────────────────────┐
    │                    Bot Main Loop                        │
    │                                                         │
    │  ┌─────────────┐    price update    ┌────────────────┐  │
    │  │  WS: market │ ────────────────>  │  check_and_    │  │
    │  │  _price     │                    │  place_buy()   │  │
    │  └─────────────┘                    └───────┬────────┘  │
    │                                             │           │
    │  ┌─────────────┐    order filled    ┌───────▼────────┐  │
    │  │  WS: order  │ ────────────────>  │  on_order_     │  │
    │  │  _updates   │                    │  update()      │  │
    │  └─────────────┘                    └───────┬────────┘  │
    │                                             │           │
    │                                     ┌───────▼────────┐  │
    │                                     │  place_sell()  │  │
    │                                     │  or restart    │  │
    │                                     └────────────────┘  │
    └─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass, field
from enum import Enum, auto

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NAMED_CONFIGS,
    BaseSDKOptions,
    DecibelWriteDex,
    PlaceOrderSuccess,
    TimeInForce,
    amount_to_chain_units,
)
from decibel._utils import get_primary_subaccount_addr
from decibel.read import DecibelReadDex
from decibel.read._market_prices import MarketPriceWsMessage  # noqa: TC001
from decibel.read._user_order_history import UserOrdersWsMessage  # noqa: TC001

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BotConfig:
    """Bot configuration — loaded from environment variables."""

    private_key: str
    api_key: str
    network: str = "testnet"
    market: str = "ETH/USD"
    buy_spread_pct: float = 1.0  # buy this % below oracle price
    sell_spread_pct: float = 1.0  # sell this % above entry price
    order_size_usd: float = 100.0  # notional order size in USD

    @classmethod
    def from_env(cls) -> BotConfig:
        private_key = os.environ.get("PRIVATE_KEY", "")
        api_key = os.environ.get("APTOS_NODE_API_KEY", "")
        if not private_key or not api_key:
            print("Error: PRIVATE_KEY and APTOS_NODE_API_KEY must be set")
            print("See docstring at top of this file for setup instructions")
            sys.exit(1)

        return cls(
            private_key=private_key,
            api_key=api_key,
            network=os.environ.get("NETWORK", "testnet"),
            market=os.environ.get("MARKET", "ETH/USD"),
            buy_spread_pct=float(os.environ.get("BUY_SPREAD_PCT", "1.0")),
            sell_spread_pct=float(os.environ.get("SELL_SPREAD_PCT", "1.0")),
            order_size_usd=float(os.environ.get("ORDER_SIZE_USD", "100")),
        )


# ---------------------------------------------------------------------------
# Bot State Machine
# ---------------------------------------------------------------------------


class BotPhase(Enum):
    WAITING_FOR_PRICE = auto()  # no position, waiting for first price to place buy
    BUY_PLACED = auto()  # buy limit order is open, waiting for fill
    SELL_PLACED = auto()  # sell limit order is open, waiting for fill


@dataclass
class BotState:
    phase: BotPhase = BotPhase.WAITING_FOR_PRICE
    latest_oracle_price: float = 0.0
    buy_order_tx: str | None = None
    buy_entry_price: float = 0.0
    sell_order_tx: str | None = None
    trades_completed: int = 0
    total_pnl: float = 0.0
    active_client_order_id: str | None = None
    _order_counter: int = field(default=0, repr=False)

    def next_client_order_id(self, side: str) -> str:
        self._order_counter += 1
        return f"bot-{side}-{self._order_counter}"


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------


class BuyLowSellHighBot:
    """Simple buy-low-sell-high bot using Decibel SDK."""

    def __init__(self, cfg: BotConfig) -> None:
        self.cfg = cfg
        self.state = BotState()
        self._shutdown = asyncio.Event()

        # SDK clients — initialized in start()
        self._read: DecibelReadDex | None = None
        self._write: DecibelWriteDex | None = None
        self._market_info: object | None = None  # PerpMarket
        self._sub_addr: str = ""

    async def start(self) -> None:
        """Initialize SDK clients, subscribe to feeds, and run the bot."""
        network_config = NAMED_CONFIGS.get(self.cfg.network)
        if network_config is None:
            log.error("Unknown network: %s (options: %s)", self.cfg.network, list(NAMED_CONFIGS))
            return

        # --- Initialize clients ---
        account = Account.load_key(PrivateKey.from_hex(self.cfg.private_key).hex())
        self._sub_addr = get_primary_subaccount_addr(
            str(account.address()),
            network_config.compat_version,
            network_config.deployment.package,
        )

        self._read = DecibelReadDex(
            network_config,
            api_key=self.cfg.api_key,
            on_ws_error=self._on_ws_error,
        )
        self._write = DecibelWriteDex(
            network_config,
            account,
            opts=BaseSDKOptions(
                node_api_key=self.cfg.api_key,
                skip_simulate=False,
                no_fee_payer=True,
                time_delta_ms=0,
            ),
        )

        # --- Load market info ---
        markets = await self._read.markets.get_all()
        self._market_info = next((m for m in markets if m.market_name == self.cfg.market), None)
        if self._market_info is None:
            log.error(
                "Market %s not found. Available: %s",
                self.cfg.market,
                [m.market_name for m in markets],
            )
            return

        log.info(
            "Market: %s (tick=%s, min_size=%s, px_dec=%d, sz_dec=%d)",
            self._market_info.market_name,
            self._market_info.tick_size,
            self._market_info.min_size,
            self._market_info.px_decimals,
            self._market_info.sz_decimals,
        )

        # --- Check account ---
        overview = await self._read.account_overview.get_by_addr(sub_addr=self._sub_addr)
        log.info("Account equity: %.2f USDC", overview.perp_equity_balance)
        if overview.perp_equity_balance < self.cfg.order_size_usd:
            log.warning(
                "Account equity (%.2f) < order size (%.2f). Bot may not be able to trade.",
                overview.perp_equity_balance,
                self.cfg.order_size_usd,
            )

        # --- Subscribe to WebSocket feeds ---
        log.info("Subscribing to price feed and order updates...")
        self._read.market_prices.subscribe_by_name(self.cfg.market, self._on_price_update)
        self._read.user_order_history.subscribe_by_addr(self._sub_addr, self._on_order_update)

        log.info("Bot started — waiting for price data...")
        log.info(
            "Config: buy %.1f%% below oracle, sell %.1f%% above entry, size $%.0f",
            self.cfg.buy_spread_pct,
            self.cfg.sell_spread_pct,
            self.cfg.order_size_usd,
        )

        # --- Run until shutdown ---
        await self._shutdown.wait()
        log.info("Shutting down...")
        await self._read.ws.close()

    def stop(self) -> None:
        """Signal the bot to shut down gracefully."""
        self._shutdown.set()

    # --- WebSocket callbacks ---

    def _on_price_update(self, msg: MarketPriceWsMessage) -> None:
        """Called on each market price update from WebSocket."""
        self.state.latest_oracle_price = msg.price.oracle_px

        if self.state.phase == BotPhase.WAITING_FOR_PRICE:
            # Schedule the buy order placement (can't await in a sync callback)
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.ensure_future(self._place_buy_order())
            )

    def _on_order_update(self, msg: UserOrdersWsMessage) -> None:
        """Called on each order status change from WebSocket."""
        update = msg.order
        order = update.order
        status = update.status

        # Only process updates for our active order
        if (
            self.state.active_client_order_id
            and order.client_order_id != self.state.active_client_order_id
        ):
            return

        log.info(
            "Order update: %s %s (id=%s, client=%s)",
            status,
            order.order_type,
            order.order_id,
            order.client_order_id,
        )

        if status == "Filled":
            if self.state.phase == BotPhase.BUY_PLACED:
                entry = order.price or self.state.latest_oracle_price
                self.state.buy_entry_price = entry
                log.info("BUY FILLED at %.2f — placing sell order...", entry)
                asyncio.get_event_loop().call_soon(
                    lambda: asyncio.ensure_future(self._place_sell_order())
                )
            elif self.state.phase == BotPhase.SELL_PLACED:
                exit_price = order.price or 0
                pnl = exit_price - self.state.buy_entry_price
                self.state.trades_completed += 1
                self.state.total_pnl += pnl
                log.info(
                    "SELL FILLED at %.2f — PnL: %.2f (total: %.2f, trades: %d)",
                    exit_price,
                    pnl,
                    self.state.total_pnl,
                    self.state.trades_completed,
                )
                # Reset — start looking for next buy
                self.state.phase = BotPhase.WAITING_FOR_PRICE
                log.info("Cycle complete — waiting for next opportunity...")

        elif status in ("Cancelled", "Rejected", "Expired"):
            log.warning("Order %s: %s — resetting to wait for price", status, update.details)
            self.state.phase = BotPhase.WAITING_FOR_PRICE

    def _on_ws_error(self, error: Exception) -> None:
        log.error("WebSocket error: %s", error)

    # --- Order placement ---

    async def _place_buy_order(self) -> None:
        """Place a limit buy order at spread below oracle price."""
        if self.state.phase != BotPhase.WAITING_FOR_PRICE:
            return
        if self.state.latest_oracle_price <= 0:
            return

        assert self._write is not None
        assert self._market_info is not None
        mkt = self._market_info

        # Calculate buy price: oracle - spread%
        buy_price_human = self.state.latest_oracle_price * (1 - self.cfg.buy_spread_pct / 100)
        buy_price = amount_to_chain_units(buy_price_human, mkt.px_decimals)

        # Calculate size from notional USD
        size_human = self.cfg.order_size_usd / self.state.latest_oracle_price
        size = amount_to_chain_units(size_human, mkt.sz_decimals)
        size = max(size, int(mkt.min_size))  # enforce minimum

        client_id = self.state.next_client_order_id("buy")
        self.state.active_client_order_id = client_id

        log.info(
            "Placing BUY: price=%.2f (oracle=%.2f, spread=%.1f%%), size=%.6f, id=%s",
            buy_price_human,
            self.state.latest_oracle_price,
            self.cfg.buy_spread_pct,
            size_human,
            client_id,
        )

        try:
            result = await self._write.place_order(
                market_name=self.cfg.market,
                price=buy_price,
                size=size,
                is_buy=True,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=False,
                client_order_id=client_id,
                tick_size=int(mkt.tick_size),
            )

            if isinstance(result, PlaceOrderSuccess):
                self.state.phase = BotPhase.BUY_PLACED
                self.state.buy_order_tx = result.transaction_hash
                log.info("BUY order placed — tx=%s", result.transaction_hash)
            else:
                log.error("BUY order failed: %s", result.error)
                self.state.phase = BotPhase.WAITING_FOR_PRICE

        except Exception:
            log.exception("Error placing buy order")
            self.state.phase = BotPhase.WAITING_FOR_PRICE

    async def _place_sell_order(self) -> None:
        """Place a limit sell order at spread above entry price."""
        if self.state.phase != BotPhase.BUY_PLACED:
            return

        assert self._write is not None
        assert self._market_info is not None
        mkt = self._market_info

        # Calculate sell price: entry + spread%
        sell_price_human = self.state.buy_entry_price * (1 + self.cfg.sell_spread_pct / 100)
        sell_price = amount_to_chain_units(sell_price_human, mkt.px_decimals)

        # Same size as the buy
        size_human = self.cfg.order_size_usd / self.state.buy_entry_price
        size = amount_to_chain_units(size_human, mkt.sz_decimals)
        size = max(size, int(mkt.min_size))

        client_id = self.state.next_client_order_id("sell")
        self.state.active_client_order_id = client_id

        log.info(
            "Placing SELL: price=%.2f (entry=%.2f, spread=%.1f%%), id=%s",
            sell_price_human,
            self.state.buy_entry_price,
            self.cfg.sell_spread_pct,
            client_id,
        )

        try:
            result = await self._write.place_order(
                market_name=self.cfg.market,
                price=sell_price,
                size=size,
                is_buy=False,
                time_in_force=TimeInForce.GoodTillCanceled,
                is_reduce_only=True,
                client_order_id=client_id,
                tick_size=int(mkt.tick_size),
            )

            if isinstance(result, PlaceOrderSuccess):
                self.state.phase = BotPhase.SELL_PLACED
                self.state.sell_order_tx = result.transaction_hash
                log.info("SELL order placed — tx=%s", result.transaction_hash)
            else:
                log.error("SELL order failed: %s", result.error)
                self.state.phase = BotPhase.WAITING_FOR_PRICE

        except Exception:
            log.exception("Error placing sell order")
            self.state.phase = BotPhase.WAITING_FOR_PRICE


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    cfg = BotConfig.from_env()
    bot = BuyLowSellHighBot(cfg)

    # Handle Ctrl+C gracefully
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, bot.stop)

    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
