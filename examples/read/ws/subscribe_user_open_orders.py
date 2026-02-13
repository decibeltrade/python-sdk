import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        if not msg.orders:
            print(f"No open orders for {SUB_ADDR}")
            return

        print(f"Open Orders for {SUB_ADDR}:\n")
        for order in msg.orders:
            print(f"  Order ID: {order.order_id}")
            print(f"    Parent: {order.parent}")
            print(f"    Market: {order.market}")
            print(f"    Client Order ID: {order.client_order_id}")
            print(f"    Orig Size: {order.orig_size}")
            print(f"    Remaining Size: {order.remaining_size}")
            print(f"    Size Delta: {order.size_delta}")
            print(f"    Price: {order.price}")
            print(f"    Is Buy: {order.is_buy}")
            print(f"    Details: {order.details}")
            print(f"    Transaction Version: {order.transaction_version}")
            print(f"    Unix MS: {order.unix_ms}")
            print(f"    Is TPSL: {order.is_tpsl}")
            print(f"    TP Order ID: {order.tp_order_id}")
            print(f"    TP Trigger Price: {order.tp_trigger_price}")
            print(f"    TP Limit Price: {order.tp_limit_price}")
            print(f"    SL Order ID: {order.sl_order_id}")
            print(f"    SL Trigger Price: {order.sl_trigger_price}")
            print(f"    SL Limit Price: {order.sl_limit_price}")
            print(f"    Order Type: {order.order_type}")
            print(f"    Trigger Condition: {order.trigger_condition}")
            print(f"    Order Direction: {order.order_direction}")
            print(f"    Is Reduce Only: {order.is_reduce_only}")
            print()

    unsubscribe = read.user_open_orders.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
