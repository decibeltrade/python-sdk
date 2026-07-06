import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

OWNER_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    tier = await read.tier.get_by_owner(owner_addr=OWNER_ADDR)
    print(f"Tier for {tier.owner}: {tier.current_tier} (rank {tier.rank})")
    for t in tier.tiers:
        print(f"  {t.name}: threshold={t.hz_threshold}, progress={t.progress}")


if __name__ == "__main__":
    asyncio.run(main())
