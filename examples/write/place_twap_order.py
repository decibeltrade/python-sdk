import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    GasPriceManagerOptions,
    PlaceOrderSuccess,
    amount_to_chain_units,
)
from decibel.read import DecibelReadDex


async def main() -> None:
    private_key = PrivateKey.from_hex(os.environ["PRIVATE_KEY"])
    account = Account.load_key(private_key.hex())

    gas = GasPriceManager(
        NETNA_CONFIG,
        opts=GasPriceManagerOptions(
            node_api_key=os.environ.get("APTOS_NODE_API_KEY"),
        ),
    )
    await gas.initialize()

    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))
    markets = await read.markets.get_all()
    ETH_market = next((m for m in markets if m.market_name == "ETH/USD"), None)

    if ETH_market is None:
        print("ETH/USD market not found")
        await gas.destroy()
        return

    size = amount_to_chain_units(2000, ETH_market.sz_decimals)

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

    result = await write.place_twap_order(
        market_name="ETH/USD",
        size=size,
        is_buy=True,
        is_reduce_only=False,
        twap_frequency_seconds=300,
        twap_duration_seconds=3600,
        client_order_id="my-twap-order-002",
    )

    if isinstance(result, PlaceOrderSuccess):
        print("TWAP order placed!")
        print(f"Order ID: {result.order_id}")
        print(f"Transaction hash: {result.transaction_hash}")
    else:
        print(f"Order failed: {result.error}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
