import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    amount_to_chain_units,
    get_market_addr,
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

    tp_trigger = amount_to_chain_units(105000.0, btc_market.px_decimals)
    tp_limit = amount_to_chain_units(104900.0, btc_market.px_decimals)
    tp_size = amount_to_chain_units(0.001, btc_market.sz_decimals)

    sl_trigger = amount_to_chain_units(88000.0, btc_market.px_decimals)
    sl_limit = amount_to_chain_units(87900.0, btc_market.px_decimals)
    sl_size = amount_to_chain_units(0.001, btc_market.sz_decimals)

    tp_order_id = 12345
    tp_result = await write.update_tp_order_for_position(
        market_addr=market_addr,
        prev_order_id=tp_order_id,
        tp_trigger_price=tp_trigger,
        tp_limit_price=tp_limit,
        tp_size=tp_size,
    )
    print(f"TP order updated. Transaction: {tp_result.get('hash')}")

    sl_order_id = 12345
    sl_result = await write.update_sl_order_for_position(
        market_addr=market_addr,
        prev_order_id=sl_order_id,
        sl_trigger_price=sl_trigger,
        sl_limit_price=sl_limit,
        sl_size=sl_size,
    )
    print(f"SL order updated. Transaction: {sl_result.get('hash')}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
