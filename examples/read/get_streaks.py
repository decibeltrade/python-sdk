import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

OWNER_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    streaks = await read.streaks.get_by_owner(owner_addr=OWNER_ADDR)
    print(f"Current streak: {streaks.current_streak}")
    print(f"Grace days: {streaks.grace_days_used}/{streaks.grace_days_available} used")
    print(f"Qualifying dates: {streaks.qualifying_dates}")


if __name__ == "__main__":
    asyncio.run(main())
