import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    response = await read.leaderboard.get_leaderboard(limit=10, sort_key="realized_pnl")

    print("Leaderboard:\n")
    for item in response.items:
        print(f"  #{item.rank}")
        print(f"    Account: {item.account}")
        print(f"    Account Value: ${item.account_value:,.2f}")
        print(f"    Realized PnL: ${item.realized_pnl:,.2f}")
        print(f"    ROI: {item.roi:.2f}%")
        print(f"    Volume: ${item.volume:,.0f}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
