import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    positions = await read.user_positions.get_by_addr(sub_addr=SUB_ADDR)

    if not positions:
        print(f"No open positions for {SUB_ADDR}")
        return

    print(f"Positions for {SUB_ADDR}:\n")
    for pos in positions:
        print(f"  Market: {pos.market}")
        print(f"    User: {pos.user}")
        print(f"    Size: {pos.size}")
        print(f"    User Leverage: {pos.user_leverage}")
        print(f"    Entry Price: {pos.entry_price}")
        print(f"    Is Isolated: {pos.is_isolated}")
        print(f"    Unrealized Funding: {pos.unrealized_funding}")
        print(f"    Estimated Liquidation Price: {pos.estimated_liquidation_price}")
        print(f"    TP Order ID: {pos.tp_order_id}")
        print(f"    TP Trigger Price: {pos.tp_trigger_price}")
        print(f"    TP Limit Price: {pos.tp_limit_price}")
        print(f"    SL Order ID: {pos.sl_order_id}")
        print(f"    SL Trigger Price: {pos.sl_trigger_price}")
        print(f"    SL Limit Price: {pos.sl_limit_price}")
        print(f"    Has Fixed Sized TPSLs: {pos.has_fixed_sized_tpsls}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
