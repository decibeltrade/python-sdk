import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    TESTNET_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    get_market_addr,
    get_primary_subaccount_addr,
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

    market_addr = get_market_addr("BTC/USD", TESTNET_CONFIG.deployment.perp_engine_global)

    subaccount_addr = get_primary_subaccount_addr(
        account.address(),
        TESTNET_CONFIG.compat_version,
        TESTNET_CONFIG.deployment.package,
    )

    tx_result = await write.configure_user_settings_for_market(
        market_addr=market_addr,
        subaccount_addr=subaccount_addr,
        is_cross=True,
        user_leverage=10,
    )

    print(f"Transaction hash: {tx_result.get('hash')}")
    print("Market settings configured: 10x leverage, cross margin mode")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
