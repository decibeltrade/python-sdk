# decibel-python-sdk

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/decibel-python-sdk)](https://pypi.org/project/decibel-python-sdk/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/decibel-python-sdk)](https://pypi.org/project/decibel-python-sdk/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/decibel-python-sdk)](https://pypi.org/project/decibel-python-sdk/)
[![CI](https://github.com/decibeltrade/python-sdk/actions/workflows/python-sdk-ci.yml/badge.svg)](https://github.com/decibeltrade/python-sdk/actions/workflows/python-sdk-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python SDK for interacting with [Decibel](https://decibel.trade), a fully on-chain trading engine built on [Aptos](https://aptos.dev).

**[📚 View Full Documentation →](https://docs.decibel.trade)**

</div>

## Installation

```bash
pip install decibel-python-sdk
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add decibel-python-sdk
```

## Configuration

Set the following environment variables:

```bash
# Required for write operations
export PRIVATE_KEY="your_private_key_hex"

# Optional: for better rate limits
export APTOS_NODE_API_KEY="your_aptos_node_api_key"
```

> **New to Decibel?** Follow the [Getting Started Guide](https://docs.decibel.trade/quickstart/overview) to create your API Wallet and get your API key from [Geomi](https://geomi.dev).

## Quick Start

### Reading Market Data

```python
import asyncio
from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

async def main():
    read = DecibelReadDex(TESTNET_CONFIG)

    # Get all markets
    markets = await read.markets.get_all()
    for market in markets:
        print(f"{market.market_name}: {market.max_leverage}x leverage")

    # Get market prices
    prices = await read.market_prices.get_all()
    for price in prices:
        print(f"{price.market}: ${price.mark_px}")

asyncio.run(main())
```

### Placing Orders

```python
import asyncio
import os
from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey
from decibel import (
    TESTNET_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    PlaceOrderSuccess,
    TimeInForce,
    amount_to_chain_units,
)
from decibel.read import DecibelReadDex

async def main():
    private_key = PrivateKey.from_hex(os.environ["PRIVATE_KEY"])
    account = Account.load_key(private_key.hex())

    gas = GasPriceManager(TESTNET_CONFIG)
    await gas.initialize()

    read = DecibelReadDex(TESTNET_CONFIG)
    markets = await read.markets.get_all()
    btc = next(m for m in markets if m.market_name == "BTC/USD")

    write = DecibelWriteDex(
        TESTNET_CONFIG,
        account,
        opts=BaseSDKOptions(gas_price_manager=gas),
    )

    result = await write.place_order(
        market_name="BTC/USD",
        price=amount_to_chain_units(100000.0, btc.px_decimals),
        size=amount_to_chain_units(0.001, btc.sz_decimals),
        is_buy=True,
        time_in_force=TimeInForce.GoodTillCanceled,
        is_reduce_only=False,
    )

    if isinstance(result, PlaceOrderSuccess):
        print(f"Order placed! ID: {result.order_id}")
    else:
        print(f"Order failed: {result.error}")

    await gas.destroy()

asyncio.run(main())
```

### WebSocket Streaming

```python
import asyncio
from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

async def main():
    read = DecibelReadDex(TESTNET_CONFIG)

    def on_price(msg):
        price = msg.price
        print(f"BTC/USD: ${price.mark_px}")

    unsubscribe = read.market_prices.subscribe_by_name("BTC/USD", on_price)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()

asyncio.run(main())
```

## Examples

See the [examples](examples) directory for complete working examples:

- **[examples/read](examples/read)** - REST API queries (markets, prices, positions, orders)
- **[examples/read/ws](examples/read/ws)** - WebSocket subscriptions (real-time streaming)
- **[examples/write](examples/write)** - Trading operations (orders, deposits, withdrawals)
  - **[examples/write/market_maker_bot.py](examples/write/market_maker_bot.py)** - Complete market maker bot implementation with inventory skew, margin management, and dry-run mode

### Market Maker Bot

The SDK includes a complete market maker bot example that demonstrates how to build a trading bot using Decibel. The bot:

- Places bid/ask quotes around the mid-price with configurable spread
- Manages inventory with skew adjustments to encourage mean-reversion
- Monitors margin usage and pauses quoting when limits are exceeded
- Supports both dry-run (simulation) and live trading modes
- Includes configurable parameters: spread, order size, inventory limits, refresh interval, and more
- Uses POST_ONLY orders for predictable fills

To run the bot, set environment variables and execute:

```bash
# Dry-run mode (no transactions)
export SUBACCOUNT_ADDRESS="0x..."
export NETWORK="testnet"
python examples/write/market_maker_bot.py --dry-run

# Live mode (requires PRIVATE_KEY as plain hex, no 0x prefix)
export PRIVATE_KEY="your_private_key_hex"
python examples/write/market_maker_bot.py \
  --market="BTC/USD" \
  --spread=0.001 \
  --order-size=0.001 \
  --max-inventory=0.01 \
  --max-margin-usage=0.5 \
  --refresh-interval=20
```

Use `python examples/write/market_maker_bot.py --help` to see all available options.

## API Reference

### Network Configs

```python
from decibel import MAINNET_CONFIG, TESTNET_CONFIG

# MAINNET_CONFIG - Production network
# TESTNET_CONFIG - Test network
```

### Read Client

```python
from decibel.read import DecibelReadDex

read = DecibelReadDex(config, api_key=None)

# Market data
read.markets.get_all()
read.market_prices.get_all()
read.market_prices.get_by_name(market_name)
read.market_depth.get_by_name(market_name, limit=50)
read.market_trades.get_by_name(market_name)
read.market_contexts.get_all()
read.candlesticks.get_by_name(market_name, interval, start_time, end_time)

# User data
read.account_overview.get_by_addr(sub_addr=sub_addr)
read.user_positions.get_by_addr(sub_addr=sub_addr)
read.user_open_orders.get_by_addr(sub_addr=sub_addr)
read.user_order_history.get_by_addr(sub_addr=sub_addr)
read.user_trade_history.get_by_addr(sub_addr=sub_addr)
read.user_bulk_orders.get_by_addr(sub_addr=sub_addr)
read.user_subaccounts.get_by_addr(owner_addr=addr)
read.user_fund_history.get_by_addr(sub_addr=sub_addr)
read.user_funding_history.get_by_addr(sub_addr=sub_addr)
read.user_active_twaps.get_by_addr(sub_addr=sub_addr)
read.user_twap_history.get_by_addr(sub_addr=sub_addr)

# Other
read.delegations.get_all(sub_addr=sub_addr)
read.leaderboard.get_leaderboard()
read.portfolio_chart.get_by_addr(sub_addr=sub_addr, time_range="7d", data_type="pnl")
read.vaults.get_vaults()
read.trading_points.get_by_owner(owner_addr=addr)
read.user_fees.get_by_addr(sub_addr=sub_addr)

# Points, streaks & tiers
read.points_leaderboard.get_points_leaderboard(limit=50, sort_key="total_amps")
read.trading_amps.get_by_owner(owner_addr=addr, season="season1", days=7)
read.tier.get_by_owner(owner_addr=addr)
read.streaks.get_by_owner(owner_addr=addr)
read.global_points_stats.get()

# Campaigns & rewards
read.campaigns.get_active()
read.campaigns.get_summary(account_address=addr)

# Referrals
read.referrals.validate_code(code)
read.referrals.get_account_referral(account)
read.referrals.get_referrer_stats(account)
read.referrals.get_user_referrals(referrer_account=account)
read.referrals.get_affiliate_codes(account)
read.referrals.get_affiliate_earnings(account)
read.referrals.redeem_code(referral_code=code, account=account)

# Withdrawal queue (indexed HTTP + on-chain fallback)
read.withdraw_queue.get_by_addr(sub_addr=sub_addr, status="Queued")
read.withdraw_queue.get_pending_withdrawals(user_addr)

# On-chain view / resource helpers
read.usdc_balance(addr)
read.token_balance(addr, token_addr, token_decimals)
read.account_balance(addr)
read.position_size(addr, market_addr)
read.get_crossed_position(addr)
read.usdc_decimals()
read.collateral_balance_decimals()
read.global_perp_engine_state()

# WebSocket subscriptions
read.market_prices.subscribe_by_name(market_name, callback)
read.market_prices.subscribe_all(callback)
read.market_depth.subscribe_by_name(market_name, aggregation_size, callback)
read.market_trades.subscribe_by_name(market_name, callback)
read.candlesticks.subscribe_by_name(market_name, interval, callback)
read.account_overview.subscribe_by_addr(sub_addr, callback)
read.user_positions.subscribe_by_addr(sub_addr, callback)
read.user_open_orders.subscribe_by_addr(sub_addr, callback)
read.user_order_history.subscribe_by_addr(sub_addr, callback)
read.user_trade_history.subscribe_by_addr(sub_addr, callback)
read.user_bulk_orders.subscribe_by_addr(sub_addr, callback)
read.user_active_twaps.subscribe_by_addr(sub_addr, callback)
read.user_notifications.subscribe_by_addr(sub_addr, callback)
read.withdraw_queue.subscribe_by_addr(sub_addr, callback)
```

### Write Client

```python
from decibel import DecibelWriteDex, TimeInForce

write = DecibelWriteDex(config, account, opts)

# Orders
write.place_order(market_name=..., price=..., size=..., is_buy=..., time_in_force=..., is_reduce_only=...)
write.update_order(order_id=..., market_addr=..., price=..., size=..., is_buy=..., time_in_force=..., is_reduce_only=...)
write.cancel_order(order_id=..., market_name=...)
write.cancel_client_order(client_order_id=..., market_name=...)
write.place_bulk_orders(market_name=..., sequence_number=..., bid_prices=..., bid_sizes=..., ask_prices=..., ask_sizes=...)
write.cancel_bulk_order(market_name=...)

# TP/SL
write.place_tp_sl_order_for_position(market_name=..., tp_price=..., sl_price=..., ...)
write.update_tp_order_for_position(market_name=..., order_id=..., new_trigger_price=..., ...)
write.update_sl_order_for_position(market_name=..., order_id=..., new_trigger_price=..., ...)

# TWAP
write.place_twap_order(market_name=..., size=..., is_buy=..., is_reduce_only=..., twap_frequency_seconds=..., twap_duration_seconds=...)
write.cancel_twap_order(market_addr=..., order_id=...)

# Collateral
write.deposit(amount)
write.withdraw(amount)
write.withdraw_non_collateral(asset_addr, amount)

# Vaults
write.deposit_to_vault(vault_address=..., amount=..., subaccount_addr=...)
write.withdraw_from_vault(vault_address=..., shares=...)

# Subaccounts
write.create_subaccount()
write.admin_create_subaccount(owner_address)
write.deactivate_subaccount(subaccount_addr=...)

# Rewards
write.claim_campaign_reward(campaign_id)
```

> A synchronous client, `DecibelWriteDexSync`, exposes the same methods without `async`/`await`.

### Utilities

```python
from decibel import (
    calculate_liquidation_price,
    LiquidationPriceInput,
    LiquidationPosition,
    LiquidationMarket,
    LiquidationMarketContext,
    to_checksum_address,
    derive_aptos_from_eth,
    derive_aptos_from_solana,
)

# Estimate a liquidation price (for an existing position or a simulated order).
liq_price = calculate_liquidation_price(
    LiquidationPriceInput(
        account_equity=1000.0,
        positions=[LiquidationPosition(market_addr="0xBTC", size=0.5, entry_price=100_000)],
        markets=[LiquidationMarket(market_addr="0xBTC", market_name="BTC/USD", max_leverage=10)],
        market_contexts=[LiquidationMarketContext(market_name="BTC/USD", mark_price=100_000)],
        target_market_addr="0xBTC",
        order_size=0,  # 0 = current position; non-zero simulates an order
    )
)

# EIP-55 checksum an Ethereum address (zero-dependency keccak-256).
checksummed = to_checksum_address("0xd8da6bf26964af9d7eed9e03e53415d37aa96045")

# Derive an Aptos address from an EVM / Solana wallet (derivable accounts).
aptos_addr = derive_aptos_from_eth("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
aptos_addr = derive_aptos_from_solana("11111111111111111111111111111111")
```

## Development

```bash
make setup                 # Install dependencies + pre-commit hooks
make                       # Run full quality pipeline (format, lint, typecheck, test)
make lint                  # Check for lint errors
make fix                   # Auto-fix lint and format issues
make typecheck             # Run pyright type checking
make test                  # Run tests
```

### Generating ABI JSON Files

The SDK uses ABI JSON files to build on-chain transactions. These are fetched from the deployed smart contracts and stored in `src/decibel/abi/json/`. They should be regenerated whenever the on-chain contracts are updated.

```bash
# Generate ABIs for a specific network (default: mainnet)
make abi
make abi NETWORK=testnet
make abi NETWORK=mainnet

# Generate ABIs for all networks
make abi-all
```

## Resources

- [📚 Documentation](https://docs.decibel.trade) - Full API documentation
- [🌐 Trading Platform](https://app.decibel.trade) - Decibel trading interface
- [💬 Discord](https://discord.gg/decibel) - Community support

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
