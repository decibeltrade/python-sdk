import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        print(f"Positions for {SUB_ADDR}:\n")
        for pos in msg.positions:
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

    unsubscribe = read.user_positions.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
