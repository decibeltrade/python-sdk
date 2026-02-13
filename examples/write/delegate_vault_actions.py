import asyncio
import os

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NETNA_CONFIG,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
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

    vault_address = "0x123..."
    delegate_to = "0x456..."
    expiration_secs = 1735689600

    tx_result = await write.delegate_vault_actions(
        vault_address=vault_address,
        account_to_delegate_to=delegate_to,
        expiration_timestamp_secs=expiration_secs,
    )

    print(f"Transaction hash: {tx_result.get('hash')}")

    await gas.destroy()


if __name__ == "__main__":
    asyncio.run(main())
