import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    PlaceBulkOrdersSuccess,
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

    px_decimals = btc_market.px_decimals
    sz_decimals = btc_market.sz_decimals

    bid_prices = [
        amount_to_chain_units(62000.0, px_decimals),
        amount_to_chain_units(60000.0, px_decimals),
    ]
    bid_sizes = [
        amount_to_chain_units(0.001, sz_decimals),
        amount_to_chain_units(0.001, sz_decimals),
    ]
    ask_prices = [
        amount_to_chain_units(101000.0, px_decimals),
        amount_to_chain_units(102000.0, px_decimals),
    ]
    ask_sizes = [
        amount_to_chain_units(0.001, sz_decimals),
        amount_to_chain_units(0.001, sz_decimals),
    ]

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

    result = await write.place_bulk_orders(
        market_name="BTC/USD",
        sequence_number=1,
        bid_prices=bid_prices,
        bid_sizes=bid_sizes,
        ask_prices=ask_prices,
        ask_sizes=ask_sizes,
    )

    if isinstance(result, PlaceBulkOrdersSuccess):
        print("Bulk orders placed successfully!")
        print(f"Transaction hash: {result.transaction_hash}")
    else:
        print(f"Bulk orders failed: {result.error}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
