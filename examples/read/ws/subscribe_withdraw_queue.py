import asyncio
import os
from typing import Any

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        print(f"Withdraw queue update for {SUB_ADDR}: {len(msg.entries)} entries")
        for entry in msg.entries:
            print(f"  [{entry.request_id}] {entry.status}: {entry.fungible_amount}")

    # Subscribe first, then seed via read.withdraw_queue.get_by_addr(...) and merge
    # with merge_withdraw_queue_entries to avoid missing events during the race window.
    unsubscribe = read.withdraw_queue.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
