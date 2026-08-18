import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    TESTNET_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    PlaceSpotOrderSuccess,
    TimeInForce,
    amount_to_chain_units,
)
from decibel.read import DecibelReadDex


async def main() -> None:
    private_key = PrivateKey.from_hex(os.environ["PRIVATE_KEY"])
    account = Account.load_key(private_key.hex())

    gas = GasPriceManager(TESTNET_CONFIG)
    await gas.initialize()

    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))
    spot_markets = await read.markets.get_all_spot()
    market = next((m for m in spot_markets if m.market_name == "APT/USDC"), None)

    if market is None:
        print("APT/USDC spot market not found")
        await gas.destroy()
        return

    # For spot rows, px_decimals is the quote asset's decimals and sz_decimals the base's.
    price = amount_to_chain_units(4.0, market.px_decimals)
    size = amount_to_chain_units(10.0, market.sz_decimals)

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

    result = await write.place_spot_order(
        market_name="APT/USDC",
        price=price,
        size=size,
        is_buy=True,
        time_in_force=TimeInForce.GoodTillCanceled,
        tick_size=market.tick_size,
    )

    if isinstance(result, PlaceSpotOrderSuccess):
        print("Spot order submitted successfully!")
        print(f"Transaction hash: {result.transaction_hash}")
        if result.pending_cbs:
            # The transaction committed, but the order is queued behind a rate-limited CBS
            # withdrawal rather than resting on the book. Poll the order endpoints for the
            # real acknowledgment instead of assuming it is live.
            print("Order is queued (pending CBS) — no order ID yet")
        else:
            print(f"Order ID: {result.order_id}")
    else:
        print(f"Spot order failed: {result.error}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
