import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    bulk_orders = await read.user_bulk_orders.get_by_addr(sub_addr=SUB_ADDR)

    if not bulk_orders:
        print(f"No bulk orders for {SUB_ADDR}")
        return

    print(f"Bulk Orders for {SUB_ADDR}:\n")
    for bulk in bulk_orders:
        print(f"  Market: {bulk.market}")
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


if __name__ == "__main__":
    asyncio.run(main())
