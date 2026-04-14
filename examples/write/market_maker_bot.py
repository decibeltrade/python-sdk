from __future__ import annotations

import argparse
import asyncio
import math
import os
from dataclasses import dataclass
from enum import StrEnum

from aptos_sdk.account import Account
from aptos_sdk.ed25519 import PrivateKey

from decibel import (
    NAMED_CONFIGS,
    BaseSDKOptions,
    DecibelWriteDex,
    GasPriceManager,
    PlaceOrderSuccess,
    TimeInForce,
    amount_to_chain_units,
    round_to_tick_size,
    round_to_valid_order_size,
)
from decibel.read import DecibelReadDex, PerpMarket


@dataclass(frozen=True)
class MMSettings:
    market_name: str = "BTC/USD"
    spread: float = 0.001
    order_size: float = 0.001
    max_inventory: float = 0.005
    skew_per_unit: float = 0.0001
    max_margin_usage: float = 0.5
    refresh_interval_s: float = 20.0
    cooldown_s: float = 1.5
    cancel_resync_s: float = 8.0
    max_cycles: int = 0
    dry_run: bool = False


class QuoteStatus(StrEnum):
    OK = "ok"
    PAUSE_NO_PRICE = "pause_no_price"
    PAUSE_INVENTORY_LIMIT = "pause_inventory_limit"
    PAUSE_SIZE_INVALID = "pause_size_invalid"


@dataclass(frozen=True)
class QuoteDecision:
    status: QuoteStatus
    bid: float | None = None
    ask: float | None = None
    size: float | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_market_name(name: str) -> str:
    return name.strip().replace("-", "/").upper()


def _resolve_market(markets: list[PerpMarket], requested_name: str) -> PerpMarket | None:
    requested = _normalize_market_name(requested_name)
    for market in markets:
        if _normalize_market_name(market.market_name) == requested:
            return market
    return None


def _compute_quotes(
    *,
    mid: float,
    inventory: float,
    market: PerpMarket,
    settings: MMSettings,
) -> QuoteDecision:
    tick_size = int(market.tick_size)
    lot_size = int(market.lot_size)
    min_size = int(market.min_size)

    if mid <= 0:
        return QuoteDecision(status=QuoteStatus.PAUSE_NO_PRICE)

    tick_human = tick_size / (10**market.px_decimals)
    min_spread = tick_human / mid
    if settings.spread < min_spread:
        raise ValueError(
            f"spread {settings.spread} is tighter than one tick ({min_spread:.8f}); "
            "increase --spread",
        )

    if abs(inventory) >= settings.max_inventory:
        return QuoteDecision(status=QuoteStatus.PAUSE_INVENTORY_LIMIT)

    if not math.isfinite(settings.order_size) or settings.order_size <= 0:
        return QuoteDecision(status=QuoteStatus.PAUSE_SIZE_INVALID)

    valid_size = round_to_valid_order_size(
        settings.order_size,
        lot_size=lot_size,
        sz_decimals=market.sz_decimals,
        min_size=min_size,
    )
    if valid_size <= 0:
        return QuoteDecision(status=QuoteStatus.PAUSE_SIZE_INVALID)

    half_spread = settings.spread / 2.0
    skew = inventory * settings.skew_per_unit

    raw_bid = mid * (1.0 - half_spread - skew)
    raw_ask = mid * (1.0 + half_spread - skew)

    bid = round_to_tick_size(
        raw_bid,
        tick_size=tick_size,
        px_decimals=market.px_decimals,
        round_up=False,
    )
    ask = round_to_tick_size(
        raw_ask,
        tick_size=tick_size,
        px_decimals=market.px_decimals,
        round_up=True,
    )

    if ask <= bid:
        ask = round_to_tick_size(
            bid + tick_human,
            tick_size=tick_size,
            px_decimals=market.px_decimals,
            round_up=True,
        )

    return QuoteDecision(
        status=QuoteStatus.OK,
        bid=bid,
        ask=ask,
        size=valid_size,
    )


async def _sync_state(
    read: DecibelReadDex,
    market: PerpMarket,
    subaccount_addr: str,
) -> tuple[float | None, float, float, list[str]]:
    overview_task = read.account_overview.get_by_addr(sub_addr=subaccount_addr)
    positions_task = read.user_positions.get_by_addr(sub_addr=subaccount_addr, limit=100)
    orders_task = read.user_open_orders.get_by_addr(sub_addr=subaccount_addr, limit=200)
    prices_task = read.market_prices.get_by_name(market.market_name)

    overview, positions, open_orders, prices = await asyncio.gather(
        overview_task,
        positions_task,
        orders_task,
        prices_task,
    )

    inventory = 0.0
    for pos in positions:
        if pos.market == market.market_addr:
            inventory = pos.size
            break

    market_order_ids = [
        order.order_id for order in open_orders.items if order.market == market.market_addr
    ]

    mid: float | None = None
    for price in prices:
        if price.market == market.market_addr:
            mid = price.mid_px
            break

    if mid is None:
        try:
            depth = await read.market_depth.get_by_name(market.market_name, limit=1)
            if depth.bids and depth.asks:
                mid = (depth.bids[0].price + depth.asks[0].price) / 2.0
        except Exception as exc:
            print(f"  warning: failed depth fallback for {market.market_name}: {exc}")

    return mid, inventory, overview.cross_margin_ratio, market_order_ids


async def _cancel_market_orders(
    write: DecibelWriteDex | None,
    market_name: str,
    order_ids: list[str],
    subaccount_addr: str,
    dry_run: bool,
) -> tuple[int, int]:
    cancelled = 0
    failed = 0
    for order_id in order_ids:
        if dry_run:
            print(f"  [dry-run] would cancel {order_id}")
            cancelled += 1
            continue
        if write is None:
            raise RuntimeError("write client is required when not in dry-run mode")
        try:
            await write.cancel_order(
                order_id=order_id,
                market_name=market_name,
                subaccount_addr=subaccount_addr,
            )
            cancelled += 1
        except Exception as exc:
            print(f"  cancel failed ({order_id}): {exc}")
            failed += 1
    return cancelled, failed


async def _place_quote(
    write: DecibelWriteDex | None,
    *,
    market: PerpMarket,
    subaccount_addr: str,
    is_buy: bool,
    price: float,
    size: float,
    dry_run: bool,
) -> None:
    side = "bid" if is_buy else "ask"
    if dry_run:
        print(f"  [dry-run] would place {side}: {price} x {size}")
        return
    if write is None:
        raise RuntimeError("write client is required in live mode")

    result = await write.place_order(
        market_name=market.market_name,
        price=amount_to_chain_units(price, market.px_decimals),
        size=amount_to_chain_units(size, market.sz_decimals),
        is_buy=is_buy,
        time_in_force=TimeInForce.PostOnly,
        is_reduce_only=False,
        subaccount_addr=subaccount_addr,
        tick_size=market.tick_size,
    )
    if isinstance(result, PlaceOrderSuccess):
        print(f"  {side} placed: {price} x {size} (tx={result.transaction_hash[:16]}...)")
    else:
        print(f"  {side} failed: {result.error}")


async def _run_cycle(
    cycle: int,
    *,
    read: DecibelReadDex,
    write: DecibelWriteDex | None,
    market: PerpMarket,
    subaccount_addr: str,
    settings: MMSettings,
) -> None:
    mid, inventory, margin_usage, open_order_ids = await _sync_state(read, market, subaccount_addr)
    print(
        f"\n[cycle {cycle}] mid={mid if mid is not None else 'N/A'} "
        f"inventory={inventory:+.6f} "
        f"margin={margin_usage * 100:.2f}% open_orders={len(open_order_ids)}"
    )

    if margin_usage > settings.max_margin_usage:
        print(
            f"  paused: margin {margin_usage * 100:.2f}% > {settings.max_margin_usage * 100:.2f}%"
        )
        return
    if mid is None:
        print("  paused: no mid price available")
        return

    decision = _compute_quotes(
        mid=mid,
        inventory=inventory,
        market=market,
        settings=settings,
    )
    if decision.status is QuoteStatus.PAUSE_INVENTORY_LIMIT:
        print(
            f"  paused: inventory {inventory:+.6f} at/above max {settings.max_inventory}; "
            "canceling resting orders only"
        )
        if (settings.dry_run or write is not None) and open_order_ids:
            await _cancel_market_orders(
                write,
                market_name=market.market_name,
                order_ids=open_order_ids,
                subaccount_addr=subaccount_addr,
                dry_run=settings.dry_run,
            )
        return
    if decision.status is QuoteStatus.PAUSE_SIZE_INVALID:
        raise ValueError("order size rounds to zero; adjust --order-size or market lot/min size")
    if decision.status is QuoteStatus.PAUSE_NO_PRICE:
        print("  paused: invalid mid price")
        return

    if decision.bid is None or decision.ask is None or decision.size is None:
        raise RuntimeError(f"unexpected quote decision: {decision.status}")

    bid, ask, size = decision.bid, decision.ask, decision.size
    print(f"  quotes: bid={bid} ask={ask} size={size}")

    failed = 0
    if (settings.dry_run or write is not None) and open_order_ids:
        cancelled, failed = await _cancel_market_orders(
            write,
            market_name=market.market_name,
            order_ids=open_order_ids,
            subaccount_addr=subaccount_addr,
            dry_run=settings.dry_run,
        )
        print(f"  cancelled={cancelled} failed={failed}")

    if failed > 0:
        await asyncio.sleep(settings.cancel_resync_s)
        still_open = await read.user_open_orders.get_by_addr(sub_addr=subaccount_addr, limit=200)
        market_still_open = [o for o in still_open.items if o.market == market.market_addr]
        if market_still_open:
            print(f"  still {len(market_still_open)} open orders, skip this cycle")
            return

    await _place_quote(
        write,
        market=market,
        subaccount_addr=subaccount_addr,
        is_buy=True,
        price=bid,
        size=size,
        dry_run=settings.dry_run,
    )
    await asyncio.sleep(settings.cooldown_s)
    await _place_quote(
        write,
        market=market,
        subaccount_addr=subaccount_addr,
        is_buy=False,
        price=ask,
        size=size,
        dry_run=settings.dry_run,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Single-file Decibel market maker bot: each cycle cancels existing market "
            "orders and places a POST_ONLY bid/ask around mid price with inventory skew."
        ),
    )
    parser.add_argument(
        "--network",
        default=os.getenv("NETWORK", "testnet"),
        choices=tuple(NAMED_CONFIGS),
        help="Network profile key from decibel.NAMED_CONFIGS",
    )
    parser.add_argument(
        "--market",
        default=os.getenv("MARKET_NAME", "BTC/USD"),
        help="Market symbol, e.g. BTC/USD",
    )
    parser.add_argument("--spread", type=float, default=float(os.getenv("MM_SPREAD", "0.001")))
    parser.add_argument(
        "--order-size",
        type=float,
        default=float(os.getenv("MM_ORDER_SIZE", "0.001")),
    )
    parser.add_argument(
        "--max-inventory",
        type=float,
        default=float(os.getenv("MM_MAX_INVENTORY", "0.005")),
    )
    parser.add_argument(
        "--skew-per-unit",
        type=float,
        default=float(os.getenv("MM_SKEW_PER_UNIT", "0.0001")),
    )
    parser.add_argument(
        "--max-margin-usage",
        type=float,
        default=float(os.getenv("MM_MAX_MARGIN", "0.5")),
        help="Pause quoting when cross_margin_ratio exceeds this value",
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=float(os.getenv("MM_REFRESH_S", "20")),
        help="Seconds between cycles",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=float(os.getenv("MM_COOLDOWN_S", "1.5")),
        help="Seconds between placing bid and ask",
    )
    parser.add_argument(
        "--cancel-resync",
        type=float,
        default=float(os.getenv("MM_CANCEL_RESYNC_S", "8")),
        help="Sleep before re-checking open orders after cancel failures",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=int(os.getenv("MAX_CYCLES", "0")),
        help="Stop after N cycles (0 = run forever)",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("DRY_RUN", False),
        help="Simulate cancels/orders without sending transactions",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()

    subaccount_addr = os.getenv("SUBACCOUNT_ADDRESS", "").strip()
    node_api_key = os.getenv("APTOS_NODE_API_KEY", "").strip() or None
    private_key_hex = os.getenv("PRIVATE_KEY", "").strip()

    if not subaccount_addr:
        print("Error: SUBACCOUNT_ADDRESS is required")
        return 1

    dry_run = args.dry_run
    if not private_key_hex:
        print("PRIVATE_KEY missing, forcing dry-run mode")
        dry_run = True

    settings = MMSettings(
        market_name=args.market,
        spread=args.spread,
        order_size=args.order_size,
        max_inventory=args.max_inventory,
        skew_per_unit=args.skew_per_unit,
        max_margin_usage=args.max_margin_usage,
        refresh_interval_s=args.refresh_interval,
        cooldown_s=args.cooldown,
        cancel_resync_s=args.cancel_resync,
        max_cycles=args.max_cycles,
        dry_run=dry_run,
    )

    config = NAMED_CONFIGS[args.network]
    read = DecibelReadDex(config, api_key=node_api_key)

    gas: GasPriceManager | None = None
    write: DecibelWriteDex | None = None
    try:
        markets = await read.markets.get_all()
        market = _resolve_market(markets, settings.market_name)
        if market is None:
            preview = ", ".join(m.market_name for m in markets[:8])
            print(f"Market '{settings.market_name}' not found. Sample: {preview}")
            return 1

        print(f"Starting MM bot on {market.market_name} ({args.network})")
        print(
            f"  spread={settings.spread} order_size={settings.order_size} "
            f"max_inventory={settings.max_inventory} skew_per_unit={settings.skew_per_unit}"
        )
        print(
            f"  max_margin_usage={settings.max_margin_usage} "
            f"refresh={settings.refresh_interval_s}s "
            f"cooldown={settings.cooldown_s}s dry_run={settings.dry_run}"
        )

        if not settings.dry_run:
            private_key = PrivateKey.from_hex(private_key_hex)
            account = Account.load_key(private_key.hex())
            gas = GasPriceManager(config)
            await gas.initialize()
            write = DecibelWriteDex(
                config,
                account,
                opts=BaseSDKOptions(
                    node_api_key=node_api_key,
                    gas_price_manager=gas,
                    skip_simulate=False,
                    no_fee_payer=True,
                    time_delta_ms=0,
                ),
            )

        cycle = 1
        while True:
            try:
                await _run_cycle(
                    cycle,
                    read=read,
                    write=write,
                    market=market,
                    subaccount_addr=subaccount_addr,
                    settings=settings,
                )
            except ValueError as exc:
                print(f"fatal config error: {exc}")
                return 2
            except Exception as exc:
                print(f"  [cycle {cycle} error] {exc}")

            if settings.max_cycles > 0 and cycle >= settings.max_cycles:
                break
            cycle += 1
            await asyncio.sleep(settings.refresh_interval_s)
    finally:
        await read.ws.close()
        if gas is not None:
            await gas.destroy()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
