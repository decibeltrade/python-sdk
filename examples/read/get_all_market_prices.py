import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    prices = await read.market_prices.get_all()

    print("All Market Prices:\n")
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
