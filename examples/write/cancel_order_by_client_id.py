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

    client_order_id = "my-limit-order-001"
    tx_result = await write.cancel_client_order(
        client_order_id=client_order_id,
        market_name="BTC/USD",
    )

    print(f"Transaction hash: {tx_result.get('hash')}")
    print(f"Order with client ID '{client_order_id}' cancelled")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
