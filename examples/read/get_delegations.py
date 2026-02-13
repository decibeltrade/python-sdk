import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    delegations = await read.delegations.get_all(sub_addr=SUB_ADDR)

    if not delegations:
        print(f"No delegations for {SUB_ADDR}")
        return

    print(f"Delegations for {SUB_ADDR}:\n")
    for delegation in delegations:
        print(f"  Delegated Account: {delegation.delegated_account}")
        print(f"    Permission Type: {delegation.permission_type}")
        print(f"    Expiration Time S: {delegation.expiration_time_s}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
