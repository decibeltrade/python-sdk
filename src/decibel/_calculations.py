"""Liquidation price calculation (concentrated margin buffer strategy).

Uses a per-position leverage factor to determine the price buffer. Matches the
on-chain liquidation price calculation; conservative for both longs and shorts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "LiquidationMarket",
    "LiquidationMarketContext",
    "LiquidationPosition",
    "LiquidationPriceInput",
    "calculate_liquidation_price",
]

# PRICE_SCALE matches the on-chain price_divisor for 6-decimal collateral (USDC).
_PRICE_SCALE = 1_000_000


@dataclass
class LiquidationPosition:
    market_addr: str
    size: float
    entry_price: float


@dataclass
class LiquidationMarket:
    market_addr: str
    market_name: str
    max_leverage: float


@dataclass
class LiquidationMarketContext:
    market_name: str
    mark_price: float


@dataclass
class LiquidationPriceInput:
    account_equity: float
    positions: list[LiquidationPosition]
    markets: list[LiquidationMarket]
    market_contexts: list[LiquidationMarketContext]
    target_market_addr: str
    # Size of simulated order (0 for current liquidation price).
    order_size: float
    # Execution price for the simulated order (defaults to mark price).
    execution_price: float | None = field(default=None)


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _maintenance_margin(
    size_abs: float,
    mark_price: float,
    max_leverage: float,
    mm_multiplier: float = 1,
    mm_divisor: float = 2,
) -> float:
    if max_leverage <= 0:
        raise ValueError(f"Invalid max_leverage: {max_leverage}. Must be positive.")
    position_notional = size_abs * mark_price
    mm_fraction = mm_multiplier / (max_leverage * mm_divisor)
    return position_notional * mm_fraction


def calculate_liquidation_price(input: LiquidationPriceInput) -> float:
    """Calculate the liquidation price for a position or simulated order.

    For ``order_size == 0`` returns the current liquidation price. For a
    non-zero order size, simulates the order and adjusts equity/entry price.
    """
    positions = input.positions
    market_by_addr = {m.market_addr: m for m in input.markets}
    context_by_name = {c.market_name: c for c in input.market_contexts}

    position = next(
        (p for p in positions if p.market_addr == input.target_market_addr),
        None,
    )
    market = market_by_addr.get(input.target_market_addr)
    if market is None:
        raise ValueError(f"Market not found for address: {input.target_market_addr}")

    market_context = context_by_name.get(market.market_name)
    if market_context is None:
        raise ValueError(
            f"Market context not found for {market.market_name}: {input.target_market_addr}"
        )

    if input.order_size == 0 and position is None:
        raise ValueError(
            f"No position found for {market.market_name}: "
            f"{input.target_market_addr} and order_size is 0"
        )

    mark_price = market_context.mark_price
    current_pos_size = position.size if position else 0.0
    new_pos_size = current_pos_size + input.order_size

    # If position would be closed or near-zero, no liquidation price.
    if abs(new_pos_size) < 1e-12:
        return 0.0

    account_equity_adjusted = input.account_equity

    if input.order_size != 0:
        execution_price = input.execution_price if input.execution_price is not None else mark_price
        current_entry_price = position.entry_price if position else execution_price
        old_position_pnl = (
            current_pos_size * (mark_price - current_entry_price) if position else 0.0
        )

        is_partial_reduction = _sign(current_pos_size) == _sign(new_pos_size) and abs(
            new_pos_size
        ) < abs(current_pos_size)

        if current_pos_size == 0 or _sign(current_pos_size) != _sign(new_pos_size):
            new_entry_price = execution_price
        elif is_partial_reduction:
            new_entry_price = current_entry_price
        else:
            new_entry_price = (
                current_pos_size * current_entry_price + input.order_size * execution_price
            ) / new_pos_size
        new_position_pnl = new_pos_size * (mark_price - new_entry_price)

        # When the order reduces or flips the position, the closed portion
        # realizes PnL at execution_price, added to collateral.
        is_reducing = current_pos_size != 0 and _sign(current_pos_size) != _sign(input.order_size)
        closed_size = min(abs(input.order_size), abs(current_pos_size)) if is_reducing else 0.0
        realized_pnl = (
            closed_size * (execution_price - current_entry_price) * _sign(current_pos_size)
        )

        pnl_difference = realized_pnl + new_position_pnl - old_position_pnl
        account_equity_adjusted += pnl_difference

    maintenance_margin_requirement = 0.0
    for pos in positions:
        if pos.market_addr == input.target_market_addr:
            continue
        pos_market = market_by_addr.get(pos.market_addr)
        if pos_market is None:
            continue
        pos_market_context = context_by_name.get(pos_market.market_name)
        if pos_market_context is None:
            continue
        maintenance_margin_requirement += _maintenance_margin(
            abs(pos.size),
            pos_market_context.mark_price,
            pos_market.max_leverage,
        )

    maintenance_margin_requirement += _maintenance_margin(
        abs(new_pos_size),
        mark_price,
        market.max_leverage,
    )

    # Margin buffer = excess equity above maintenance margin.
    margin_buffer = account_equity_adjusted - maintenance_margin_requirement
    if margin_buffer <= 0:
        return mark_price

    is_long = new_pos_size > 0
    abs_new_size = abs(new_pos_size)

    mmr_ratio = 1 / (market.max_leverage * 2)
    leverage_factor = 1 - mmr_ratio if is_long else 1 + mmr_ratio
    # Floor truncation to 6 decimal places matches on-chain rounding.
    price_buffer = (
        math.floor((margin_buffer / (abs_new_size * leverage_factor)) * _PRICE_SCALE) / _PRICE_SCALE
    )

    liquidation_price = mark_price - price_buffer if is_long else mark_price + price_buffer
    return max(liquidation_price, 0.0)
