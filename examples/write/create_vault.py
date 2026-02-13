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
    extract_vault_address_from_create_tx,
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
            skip_simulate=True,
            no_fee_payer=True,
            time_delta_ms=0,
        ),
    )

    tx_result = await write.create_vault(
        {  # pyright: ignore[reportArgumentType]
            "vault_name": "My Trading Vault",
            "vault_description": "A vault for automated trading strategies",
            "vault_social_links": ["https://twitter.com/myproject"],
            "vault_share_symbol": "MTV",
            "fee_bps": 200,
            "fee_interval_s": 2592000,  # 30 days (minimum)
            "contribution_lockup_duration_s": 86400 * 7,
            "initial_funding": amount_to_chain_units(1000.0),
            "accepts_contributions": True,
            "delegate_to_creator": True,
        }
    )

    print(f"Transaction hash: {tx_result.get('hash')}")

    vault_address = extract_vault_address_from_create_tx(tx_result)
    print(f"Vault created at: {vault_address}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
