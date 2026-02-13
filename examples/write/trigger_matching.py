import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    get_market_addr,
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

    market_addr = get_market_addr("BTC/USD", NETNA_CONFIG.deployment.perp_engine_global)

    result = await write.trigger_matching(
        market_addr=market_addr,
        max_work_unit=100,
    )

    print(f"Success: {result['success']}")
    print(f"Transaction hash: {result['transactionHash']}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
