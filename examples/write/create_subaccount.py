import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
)


async def main() -> None:
    private_key = PrivateKey.from_hex(os.environ["PRIVATE_KEY"])
    account = Account.load_key(private_key.hex())

    gas = GasPriceManager(NETNA_CONFIG)
    await gas.initialize()

    write = DecibelWriteDex(
        NETNA_CONFIG,
        account,
        opts=BaseSDKOptions(
            node_api_key=os.environ.get("APTOS_NODE_API_KEY"),
            gas_price_manager=gas,
            skip_simulate=False,
            no_fee_payer=True,
            time_delta_ms=0,
        ),
    )

    tx_result = await write.create_subaccount()

    print(f"Transaction hash: {tx_result.get('hash')}")

    events = tx_result.get("events", [])
    for event in events:
        event_type = event.get("type", "")
        if "SubaccountCreatedEvent" in event_type:
            event_data = event.get("data", {})
            subaccount_addr = event_data.get("subaccount")
            print(f"New subaccount created: {subaccount_addr}")
            break

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
