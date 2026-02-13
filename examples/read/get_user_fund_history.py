import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    response = await read.user_fund_history.get_by_addr(sub_addr=SUB_ADDR, limit=10)

    if not response.funds:
        print(f"No fund history for {SUB_ADDR}")
        return

    print(f"Fund History for {SUB_ADDR}:\n")
    for fund in response.funds:
        print(f"  Movement Type: {fund.movement_type}")
        print(f"    Amount: {fund.amount}")
        print(f"    Balance After: {fund.balance_after}")
        print(f"    Timestamp: {fund.timestamp}")
        print(f"    Transaction Version: {fund.transaction_version}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
