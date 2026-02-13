# decibel-python-sdk

<div align="center">

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: pyright](https://img.shields.io/badge/type%20checked-pyright-blue.svg)](https://github.com/microsoft/pyright)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
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
from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

async def main():
    read = DecibelReadDex(NETNA_CONFIG)

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
    NETNA_CONFIG,
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

    gas = GasPriceManager(NETNA_CONFIG)
    await gas.initialize()

    read = DecibelReadDex(NETNA_CONFIG)
    markets = await read.markets.get_all()
    btc = next(m for m in markets if m.market_name == "BTC/USD")

    write = DecibelWriteDex(
        NETNA_CONFIG,
        account,
        opts=BaseSDKOptions(gas_price_manager=gas),
    )

    result = await write.place_order(
        market_name="BTC/USD",
        price=amount_to_chain_units(100000.0, btc.px_decimals),
        size=amount_to_chain_units(0.001, btc.sz_decimals),
        is_buy=True,
        time_in_force=TimeInForce.GoodTilCancelled,
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
from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

async def main():
    read = DecibelReadDex(NETNA_CONFIG)

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

## API Reference

### Network Configs

```python
from decibel import NETNA_CONFIG, TESTNET_CONFIG

# NETNA_CONFIG - Dev Network
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
read.candlesticks.get_by_name(market_name, interval, start_time, end_time)

# User data
read.user_positions.get_by_addr(sub_addr)
read.user_open_orders.get_by_addr(sub_addr)
read.user_order_history.get_by_addr(sub_addr)
read.user_trade_history.get_by_addr(sub_addr)
read.account_overview.get_by_addr(sub_addr)

# WebSocket subscriptions
read.market_prices.subscribe_by_name(market_name, callback)
read.market_depth.subscribe_by_name(market_name, aggregation_size, callback)
read.user_positions.subscribe_by_addr(sub_addr, callback)
```

### Write Client

```python
from decibel import DecibelWriteDex, TimeInForce

write = DecibelWriteDex(config, account, opts)

# Orders
write.place_order(market_name, price, size, is_buy, time_in_force, is_reduce_only)
write.cancel_order(market_name, order_id)
write.cancel_order_by_client_id(market_name, client_order_id)

# TP/SL
write.place_tp_sl_for_position(market_name, tp_price, sl_price, ...)
write.update_tp_order(market_name, order_id, new_trigger_price, ...)
write.update_sl_order(market_name, order_id, new_trigger_price, ...)

# Collateral
write.deposit(amount)
write.withdraw(amount)
```

## Development

```bash
uv sync --all-extras       # Install dependencies
uv run pre-commit install  # Setup pre-commit hooks
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run pyright             # Type check
```

## Resources

- [📚 Documentation](https://docs.decibel.trade) - Full API documentation
- [🌐 Trading Platform](https://app.decibel.trade) - Decibel trading interface
- [💬 Discord](https://discord.gg/decibel) - Community support

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
