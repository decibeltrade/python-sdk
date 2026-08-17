import asyncio
import os

from decibel import TESTNET_CONFIG, get_spot_market_addr
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    markets = await read.markets.get_all_spot()

    print("All Spot Markets:\n")
    for market in markets:
        # Spot rows reuse the perp row shape: sz_decimals is the base asset's decimals and
        # px_decimals the quote's; max_leverage / max_open_interest are always 0.
        derived_addr = get_spot_market_addr(market.market_name, TESTNET_CONFIG.deployment.package)

        print(f"  Market Name: {market.market_name}")
        print(f"    Market Addr: {market.market_addr}")
        print(f"    Derived Addr Matches: {derived_addr == market.market_addr}")
        print(f"    Base Decimals: {market.sz_decimals}")
        print(f"    Quote Decimals: {market.px_decimals}")
        print(f"    Tick Size: {market.tick_size}")
        print(f"    Lot Size: {market.lot_size}")
        print(f"    Min Size: {market.min_size}")
        print()

    if not markets:
        print("  (no spot markets registered on this network)")


if __name__ == "__main__":
    asyncio.run(main())
