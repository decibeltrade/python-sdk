import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    stats = await read.global_points_stats.get()
    print(f"Total users: {stats.total_users}")
    print(f"Total amps distributed: {stats.total_amps_distributed}")


if __name__ == "__main__":
    asyncio.run(main())
