import asyncio
import os

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x456..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    response = await read.user_order_history.get_by_addr(sub_addr=SUB_ADDR, limit=10)

    if not response.items:
        print(f"No order history for {SUB_ADDR}")
        return

    print(f"Order History for {SUB_ADDR}:\n")
    for order in response.items:
        print(f"  Order ID: {order.order_id}")
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


if __name__ == "__main__":
    asyncio.run(main())
