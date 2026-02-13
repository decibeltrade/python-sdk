import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    market_name = "BTC/USD"

    def on_data(msg: Any) -> None:
        print(f"Market Trades for {market_name}:\n")
        for trade in msg.trades:
            print(f"  Account: {trade.account}")
            print(f"    Market: {trade.market}")
            print(f"    Action: {trade.action}")
            print(f"    Size: {trade.size}")
            print(f"    Price: {trade.price}")
            print(f"    Is Profit: {trade.is_profit}")
            print(f"    Realized PnL Amount: {trade.realized_pnl_amount}")
            print(f"    Is Funding Positive: {trade.is_funding_positive}")
            print(f"    Realized Funding Amount: {trade.realized_funding_amount}")
            print(f"    Is Rebate: {trade.is_rebate}")
            print(f"    Fee Amount: {trade.fee_amount}")
            print(f"    Transaction Unix MS: {trade.transaction_unix_ms}")
            print(f"    Transaction Version: {trade.transaction_version}")
            print()

    unsubscribe = read.market_trades.subscribe_by_name(market_name, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
