import asyncio
import os
from typing import Any

from decibel import NETNA_CONFIG
from decibel.read import DecibelReadDex

SUB_ADDR = "0x123..."


async def main() -> None:
    read = DecibelReadDex(NETNA_CONFIG, api_key=os.environ.get("APTOS_NODE_API_KEY"))

    def on_data(msg: Any) -> None:
        overview = msg.account_overview
        print(f"Account Overview for {SUB_ADDR}:\n")
        print(f"  Perp Equity Balance: {overview.perp_equity_balance}")
        print(f"  Unrealized PnL: {overview.unrealized_pnl}")
        print(f"  Unrealized Funding Cost: {overview.unrealized_funding_cost}")
        print(f"  Cross Margin Ratio: {overview.cross_margin_ratio}")
        print(f"  Maintenance Margin: {overview.maintenance_margin}")
        print(f"  Cross Account Leverage Ratio: {overview.cross_account_leverage_ratio}")
        print(f"  Net Deposits: {overview.net_deposits}")
        print(f"  All Time Return: {overview.all_time_return}")
        print(f"  PnL 90d: {overview.pnl_90d}")
        print(f"  Sharpe Ratio: {overview.sharpe_ratio}")
        print(f"  Max Drawdown: {overview.max_drawdown}")
        print(f"  Weekly Win Rate 12w: {overview.weekly_win_rate_12w}")
        print(f"  Average Cash Position: {overview.average_cash_position}")
        print(f"  Average Leverage: {overview.average_leverage}")
        print(f"  Cross Account Position: {overview.cross_account_position}")
        print(f"  Total Margin: {overview.total_margin}")
        print(f"  USDC Cross Withdrawable Balance: {overview.usdc_cross_withdrawable_balance}")
        print(f"  USDC Isolated Withdrawable: {overview.usdc_isolated_withdrawable_balance}")
        print(f"  Realized PnL: {overview.realized_pnl}")
        print(f"  Liquidation Fees Paid: {overview.liquidation_fees_paid}")
        print(f"  Liquidation Losses: {overview.liquidation_losses}")
        print()

    unsubscribe = read.account_overview.subscribe_by_addr(SUB_ADDR, on_data)

    await asyncio.sleep(30)
    unsubscribe()
    await read.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
