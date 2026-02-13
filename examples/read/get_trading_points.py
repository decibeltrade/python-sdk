import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

OWNER_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    points = await read.trading_points.get_by_owner(owner_addr=OWNER_ADDR)

    print(f"Trading Points for {points.owner}:")
    print(f"  Total Points: {points.total_points}")

    if points.breakdown:
        print("\n  Breakdown by Subaccount:")
        for sub in points.breakdown:
            print(f"    {sub.account}: {sub.points}")


if __name__ == "__main__":
    asyncio.run(main())
