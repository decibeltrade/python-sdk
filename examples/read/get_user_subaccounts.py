import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

OWNER_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    subaccounts = await read.user_subaccounts.get_by_addr(owner_addr=OWNER_ADDR)

    print(f"Subaccounts for {OWNER_ADDR}:\n")
    for sub in subaccounts:
        print(f"  Subaccount Address: {sub.subaccount_address}")
        print(f"    Primary Account Address: {sub.primary_account_address}")
        print(f"    Is Primary: {sub.is_primary}")
        print(f"    Is Active: {sub.is_active}")
        print(f"    Custom Label: {sub.custom_label}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
