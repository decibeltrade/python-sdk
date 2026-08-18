import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value}"


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    contexts = await read.spot_asset_contexts.get_all()

    print("Spot Asset Contexts:\n")
    for ctx in contexts:
        # last_price/high/low are None with no trades in the last 24h, mid is None without
        # two-sided resting liquidity, and prev_day_price is None before the 24h boundary.
        if ctx.last_price is not None and ctx.prev_day_price:
            change_24h = f"{(ctx.last_price - ctx.prev_day_price) / ctx.prev_day_price * 100:.2f}%"
        else:
            change_24h = "n/a"

        print(f"  {ctx.name} ({ctx.ticker_id})")
        print(f"    Market Addr: {ctx.market_addr}")
        print(f"    Base Asset: {ctx.base_asset_addr} ({ctx.base_decimals} decimals)")
        print(f"    Quote Asset: {ctx.quote_asset_addr} ({ctx.quote_decimals} decimals)")
        print(f"    Last Price: {_fmt(ctx.last_price)}")
        print(f"    Mid: {_fmt(ctx.mid)}")
        print(f"    24h Change: {change_24h}")
        print(f"    24h High / Low: {_fmt(ctx.high_24h)} / {_fmt(ctx.low_24h)}")
        print(f"    24h Volume (base): {ctx.volume_24h_base}")
        print(f"    24h Volume (quote): {ctx.volume_24h_quote}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
