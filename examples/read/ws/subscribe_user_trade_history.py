import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        print(f"Trade History for {SUB_ADDR}:\n")
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

    unsubscribe = read.user_trade_history.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
