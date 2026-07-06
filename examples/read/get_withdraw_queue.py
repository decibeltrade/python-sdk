import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    page = await read.withdraw_queue.get_by_addr(sub_addr=SUB_ADDR, status="Queued")
    print(f"Withdraw queue entries: {page.total_count}")
    for entry in page.items:
        print(f"  [{entry.request_id}] {entry.status}: {entry.fungible_amount}")

    pending = await read.withdraw_queue.get_pending_withdrawals(SUB_ADDR)
    print(f"On-chain pending: {len(pending)}")


if __name__ == "__main__":
    asyncio.run(main())
