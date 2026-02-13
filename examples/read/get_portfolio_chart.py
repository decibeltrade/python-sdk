import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    chart = await read.portfolio_chart.get_by_addr(
        sub_addr=SUB_ADDR,
        time_range="24h",
        data_type="pnl",
    )

    print(f"Portfolio Chart for {SUB_ADDR}:\n")
    for item in chart:
        print(f"  Timestamp: {item.timestamp}")
        print(f"    Data Points: {item.data_points}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
