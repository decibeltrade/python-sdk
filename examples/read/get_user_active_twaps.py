import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    twaps = await read.user_active_twaps.get_by_addr(sub_addr=SUB_ADDR)

    if not twaps:
        print(f"No active TWAPs for {SUB_ADDR}")
        return

    print(f"Active TWAPs for {SUB_ADDR}:\n")
    for twap in twaps:
        print(f"  Order ID: {twap.order_id}")
        print(f"    Market: {twap.market}")
        print(f"    Is Buy: {twap.is_buy}")
        print(f"    Client Order ID: {twap.client_order_id}")
        print(f"    Is Reduce Only: {twap.is_reduce_only}")
        print(f"    Start Unix MS: {twap.start_unix_ms}")
        print(f"    Frequency S: {twap.frequency_s}")
        print(f"    Duration S: {twap.duration_s}")
        print(f"    Orig Size: {twap.orig_size}")
        print(f"    Remaining Size: {twap.remaining_size}")
        print(f"    Status: {twap.status}")
        print(f"    Transaction Unix MS: {twap.transaction_unix_ms}")
        print(f"    Transaction Version: {twap.transaction_version}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
