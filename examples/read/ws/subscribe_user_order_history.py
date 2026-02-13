import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        inner = msg.order
        order = inner.order
        print(f"Order Update for {SUB_ADDR}:\n")
        print(f"  Status: {inner.status}")
        print(f"  Details: {inner.details}")
        print("  Order:")
        print(f"    Order ID: {order.order_id}")
        print(f"    Parent: {order.parent}")
        print(f"    Market: {order.market}")
        print(f"    Client Order ID: {order.client_order_id}")
        print(f"    Status: {order.status}")
        print(f"    Order Type: {order.order_type}")
        print(f"    Trigger Condition: {order.trigger_condition}")
        print(f"    Order Direction: {order.order_direction}")
        print(f"    Orig Size: {order.orig_size}")
        print(f"    Remaining Size: {order.remaining_size}")
        print(f"    Size Delta: {order.size_delta}")
        print(f"    Price: {order.price}")
        print(f"    Is Buy: {order.is_buy}")
        print(f"    Is Reduce Only: {order.is_reduce_only}")
        print(f"    Details: {order.details}")
        print(f"    Is TPSL: {order.is_tpsl}")
        print(f"    TP Order ID: {order.tp_order_id}")
        print(f"    TP Trigger Price: {order.tp_trigger_price}")
        print(f"    TP Limit Price: {order.tp_limit_price}")
        print(f"    SL Order ID: {order.sl_order_id}")
        print(f"    SL Trigger Price: {order.sl_trigger_price}")
        print(f"    SL Limit Price: {order.sl_limit_price}")
        print(f"    Transaction Version: {order.transaction_version}")
        print(f"    Unix MS: {order.unix_ms}")
        print()

    unsubscribe = read.user_order_history.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
