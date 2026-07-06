import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

ACCOUNT_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    active = await read.campaigns.get_active()
    print(f"Active campaigns: {len(active)}")
    for c in active:
        print(f"  [{c.campaign_id}] {c.title} ({c.status})")

    summary = await read.campaigns.get_summary(account_address=ACCOUNT_ADDR)
    print(f"\nLifetime earned: {summary.lifetime_earned}, ready to claim: {summary.ready_to_claim}")


if __name__ == "__main__":
    asyncio.run(main())
