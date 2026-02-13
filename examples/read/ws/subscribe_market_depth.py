import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    market_name = "BTC/USD"
    aggregation_size = 1

    def on_data(msg: Any) -> None:
        print(f"Market Depth for {market_name}:\n")
        print(f"  Market: {msg.market}")
        print(f"  Unix MS: {msg.unix_ms}")
        print(f"  Bids ({len(msg.bids)}):")
        for bid in msg.bids:
            print(f"    Price: {bid.price}")
            print(f"    Size: {bid.size}")
        print(f"  Asks ({len(msg.asks)}):")
        for ask in msg.asks:
            print(f"    Price: {ask.price}")
            print(f"    Size: {ask.size}")
        print()

    unsubscribe = read.market_depth.subscribe_by_name(market_name, aggregation_size, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
