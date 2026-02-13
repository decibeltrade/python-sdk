import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import CandlestickInterval, DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    market_name = "BTC/USD"
    interval = CandlestickInterval.ONE_MINUTE

    def on_data(msg: Any) -> None:
        candle = msg.candle
        print(f"Candlestick for {market_name}:\n")
        print(f"  Time Start: {candle.time_start}")
        print(f"  Time End: {candle.time_end}")
        print(f"  Interval: {candle.interval}")
        print(f"  Open Price: {candle.open_price}")
        print(f"  High: {candle.high}")
        print(f"  Low: {candle.low}")
        print(f"  Close: {candle.close}")
        print(f"  Volume: {candle.volume}")
        print()

    unsubscribe = read.candlesticks.subscribe_by_name(market_name, interval, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
