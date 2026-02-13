import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        print(f"Received {len(msg.prices)} market prices:\n")
        for price in msg.prices:
            print(f"  Market: {price.market}")
            print(f"    Mark Price: {price.mark_px}")
            print(f"    Mid Price: {price.mid_px}")
            print(f"    Oracle Price: {price.oracle_px}")
            print(f"    Funding Rate Bps: {price.funding_rate_bps}")
            print(f"    Is Funding Positive: {price.is_funding_positive}")
            print(f"    Open Interest: {price.open_interest}")
            print(f"    Transaction Unix MS: {price.transaction_unix_ms}")
            print()

    unsubscribe = read.market_prices.subscribe_all(on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
