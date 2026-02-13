import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    markets = await read.markets.get_all()

    print("All Markets:\n")
    for market in markets:
        print(f"  Market Name: {market.market_name}")
        print(f"    Market Addr: {market.market_addr}")
        print(f"    Sz Decimals: {market.sz_decimals}")
        print(f"    Px Decimals: {market.px_decimals}")
        print(f"    Max Leverage: {market.max_leverage}")
        print(f"    Tick Size: {market.tick_size}")
        print(f"    Min Size: {market.min_size}")
        print(f"    Lot Size: {market.lot_size}")
        print(f"    Max Open Interest: {market.max_open_interest}")
        print(f"    Mode: {market.mode}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
