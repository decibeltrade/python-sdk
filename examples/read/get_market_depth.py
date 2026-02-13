import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    market_name = "BTC/USD"
    depth = await read.market_depth.get_by_name(market_name, limit=10)

    print(f"Market Depth for {market_name}:\n")
    print(f"  Unix MS: {depth.unix_ms}")

    print("  Bids:")
    for bid in depth.bids:
        print(f"    Price: {bid.price}")
        print(f"    Size: {bid.size}")
        print()

    print("  Asks:")
    for ask in depth.asks:
        print(f"    Price: {ask.price}")
        print(f"    Size: {ask.size}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
