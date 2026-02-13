import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        notif = msg.notification
        print(f"Notification for {SUB_ADDR}:\n")
        print(f"  Account: {notif.account}")
        print(f"  Notification Type: {notif.notification_type}")
        if notif.notification_metadata:
            meta = notif.notification_metadata
            print("  Notification Metadata:")
            print(f"    Trigger Price: {meta.trigger_price}")
            print(f"    Reason: {meta.reason}")
            print(f"    Amount: {meta.amount}")
            print(f"    Filled Size: {meta.filled_size}")
        if notif.order:
            print("  Order:")
            print(f"    Order ID: {notif.order.order_id}")
            print(f"    Market: {notif.order.market}")
        if notif.twap:
            print("  TWAP:")
            print(f"    Order ID: {notif.twap.order_id}")
            print(f"    Market: {notif.twap.market}")
        print()

    unsubscribe = read.user_notifications.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
