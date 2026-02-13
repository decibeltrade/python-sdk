import asyncio

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG)

    addresses = await read.markets.list_market_addresses()

    print(f"Found {len(addresses)} market addresses:\n")
    for addr in addresses:
        name = await read.markets.market_name_by_address(addr)
        print(f"  {name}: {addr}")


if __name__ == "__main__":
    asyncio.run(main())
