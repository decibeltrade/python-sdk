import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    market_name = "BTC/USD"
    prices = await read.market_prices.get_by_name(market_name)

    if not prices:
        print(f"No price data for {market_name}")
        return

    print(f"Market Prices for {market_name}:\n")
    for price in prices:
        print(f"  Market: {price.market}")
        print(f"    Mark Px: {price.mark_px}")
        print(f"    Mid Px: {price.mid_px}")
        print(f"    Oracle Px: {price.oracle_px}")
        print(f"    Funding Rate BPS: {price.funding_rate_bps}")
        print(f"    Is Funding Positive: {price.is_funding_positive}")
        print(f"    Open Interest: {price.open_interest}")
        print(f"    Transaction Unix MS: {price.transaction_unix_ms}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
