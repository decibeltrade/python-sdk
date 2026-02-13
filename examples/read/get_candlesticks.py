import asyncio
import os
from datetime import UTC, datetime

from decibel import NETNA_CONFIG
from decibel.read import CandlestickInterval, DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    market_name = "BTC/USD"
    interval = CandlestickInterval.ONE_HOUR

    # Get last 24 hours of candlesticks
    now = int(datetime.now(tz=UTC).timestamp() * 1000)
    start_time = now - (24 * 60 * 60 * 1000)  # 24 hours ago

    candles = await read.candlesticks.get_by_name(
        market_name,
        interval=interval,
        start_time=start_time,
        end_time=now,
    )

    print(f"Candlesticks for {market_name} ({interval.value}):\n")
    for candle in candles:
        print(f"  Time Start: {candle.time_start}")
        print(f"    Time End: {candle.time_end}")
        print(f"    Interval: {candle.interval}")
        print(f"    Open Price: {candle.open_price}")
        print(f"    High: {candle.high}")
        print(f"    Low: {candle.low}")
        print(f"    Close: {candle.close}")
        print(f"    Volume: {candle.volume}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
