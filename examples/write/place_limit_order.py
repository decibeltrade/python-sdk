import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    PlaceOrderSuccess,
    TimeInForce,
    amount_to_chain_units,
)
from decibel.read import DecibelReadDex


async def main() -> None:
    private_key = PrivateKey.from_hex(os.environ["PRIVATE_KEY"])
    account = Account.load_key(private_key.hex())

    gas = GasPriceManager(NETNA_CONFIG)
    await gas.initialize()

    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))
    markets = await read.markets.get_all()
    btc_market = next((m for m in markets if m.market_name == "BTC/USD"), None)

    if btc_market is None:
        print("BTC/USD market not found")
        await gas.destroy()
        return

    price = amount_to_chain_units(80000.0, btc_market.px_decimals)
    size = amount_to_chain_units(0.001, btc_market.sz_decimals)
    tick_size = btc_market.tick_size

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

    result = await write.place_order(
        market_name="BTC/USD",
        price=price,
        size=size,
        is_buy=True,
        time_in_force=TimeInForce.GoodTillCanceled,
        is_reduce_only=False,
        client_order_id="my-limit-order-001",
        tick_size=tick_size,
    )

    if isinstance(result, PlaceOrderSuccess):
        print("Order placed successfully!")
        print(f"Order ID: {result.order_id}")
        print(f"Transaction hash: {result.transaction_hash}")
    else:
        print(f"Order failed: {result.error}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
