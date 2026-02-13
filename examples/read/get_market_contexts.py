import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    contexts = await read.market_contexts.get_all()

    print("All Market Contexts:\n")
    for ctx in contexts:
        print(f"  Market: {ctx.market}")
        print(f"    Volume 24h: {ctx.volume_24h}")
        print(f"    Open Interest: {ctx.open_interest}")
        print(f"    Previous Day Price: {ctx.previous_day_price}")
        print(f"    Price Change Pct 24h: {ctx.price_change_pct_24h}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
