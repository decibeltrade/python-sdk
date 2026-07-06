import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    page = await read.points_leaderboard.get_points_leaderboard(limit=10, sort_key="total_amps")
    print(f"Points leaderboard (total {page.total_count}):")
    for item in page.items:
        print(f"  #{item.rank} {item.owner}: {item.total_amps} amps")


if __name__ == "__main__":
    asyncio.run(main())
