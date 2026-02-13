import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        inner = msg.bulk_order
        bulk = inner.bulk_order
        print(f"Bulk Order Update for {SUB_ADDR}:\n")
        print(f"  Status: {inner.status}")
        print(f"  Details: {inner.details}")
        print("  Bulk Order:")
        print(f"    Market: {bulk.market}")
        print(f"    Sequence Number: {bulk.sequence_number}")
        print(f"    Previous Seq Num: {bulk.previous_seq_num}")
        print(f"    Bid Prices: {bulk.bid_prices}")
        print(f"    Bid Sizes: {bulk.bid_sizes}")
        print(f"    Ask Prices: {bulk.ask_prices}")
        print(f"    Ask Sizes: {bulk.ask_sizes}")
        print(f"    Cancelled Bid Prices: {bulk.cancelled_bid_prices}")
        print(f"    Cancelled Bid Sizes: {bulk.cancelled_bid_sizes}")
        print(f"    Cancelled Ask Prices: {bulk.cancelled_ask_prices}")
        print(f"    Cancelled Ask Sizes: {bulk.cancelled_ask_sizes}")
        print()

    unsubscribe = read.user_bulk_orders.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
