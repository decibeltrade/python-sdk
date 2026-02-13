import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    response = await read.user_funding_history.get_by_addr(sub_addr=SUB_ADDR, limit=10)

    if not response.items:
        print(f"No funding history for {SUB_ADDR}")
        return

    print(f"Funding History for {SUB_ADDR}:\n")
    for funding in response.items:
        print(f"  Market: {funding.market}")
        print(f"    Action: {funding.action}")
        print(f"    Size: {funding.size}")
        print(f"    Is Funding Positive: {funding.is_funding_positive}")
        print(f"    Realized Funding Amount: {funding.realized_funding_amount}")
        print(f"    Is Rebate: {funding.is_rebate}")
        print(f"    Fee Amount: {funding.fee_amount}")
        print(f"    Transaction Unix MS: {funding.transaction_unix_ms}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
