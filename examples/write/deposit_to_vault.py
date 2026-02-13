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
    get_primary_subaccount_addr,
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

    subaccount_addr = get_primary_subaccount_addr(
        account.address(),
        NETNA_CONFIG.compat_version,
        NETNA_CONFIG.deployment.package,
    )

    vault_address = "0x123..."
    amount = amount_to_chain_units(500.0)

    tx_result = await write.deposit_to_vault(
        vault_address=vault_address,
        amount=amount,
        subaccount_addr=subaccount_addr,
    )

    print(f"Transaction hash: {tx_result.get('hash')}")
    print(f"Deposited {amount} USDC to vault {vault_address}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
