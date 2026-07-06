import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

OWNER_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    amps = await read.trading_amps.get_by_owner(owner_addr=OWNER_ADDR, days=7)
    print(f"Trading amps for {amps.owner}: {amps.total_amps}")
    if amps.breakdown:
        for sub in amps.breakdown:
            print(f"  {sub.account}: {sub.total_amps}")


if __name__ == "__main__":
    asyncio.run(main())
