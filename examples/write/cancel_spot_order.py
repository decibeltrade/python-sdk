import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    TESTNET_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
)


async def main() -> None:
    private_key = PrivateKey.from_hex(os.environ["PRIVATE_KEY"])
    account = Account.load_key(private_key.hex())

    gas = GasPriceManager(TESTNET_CONFIG)
    await gas.initialize()

    write = DecibelWriteDex(
        TESTNET_CONFIG,
        account,
        opts=BaseSDKOptions(
            node_api_key=os.environ.get("APTOS_NODE_API_KEY"),
            gas_price_manager=gas,
            skip_simulate=False,
            no_fee_payer=True,
            time_delta_ms=0,
        ),
    )

    # Spot markets can be addressed by name (derived via `get_spot_market_addr`) or by
    # passing `market_addr=` directly.
    order_id = 12345
    tx_result = await write.cancel_spot_order(
        order_id=order_id,
        market_name="APT/USDC",
    )

    print(f"Transaction hash: {tx_result.get('hash')}")
    print(f"Spot order {order_id} cancelled")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
