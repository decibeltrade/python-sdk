import asyncio
import os

from decibel import TESTNET_CONFIG
from decibel.read import DecibelReadDex

ACCOUNT_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(TESTNET_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    stats = await read.referrals.get_referrer_stats(ACCOUNT_ADDR)
    print(f"Total referrals: {stats.total_referrals}, codes: {stats.codes}")

    referred = await read.referrals.get_user_referrals(referrer_account=ACCOUNT_ADDR, limit=10)
    for user in referred:
        print(f"  {user.account} via {user.referral_code}")


if __name__ == "__main__":
    asyncio.run(main())
