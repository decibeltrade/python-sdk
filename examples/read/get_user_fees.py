import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    fees = await read.user_fees.get_by_addr(sub_addr=SUB_ADDR)
    print(f"Taker rate: {fees.user_taker_rate}, maker rate: {fees.user_maker_rate}")
    print(f"Fee tier: {fees.fee_tier}")


if __name__ == "__main__":
    asyncio.run(main())
