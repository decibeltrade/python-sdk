"""Mirror of the Move ``payout_math`` / ``funded_first_trade`` / ``campaign_lock`` defaults.

All amounts are raw USDC (x10^6) integers, matching the on-chain u64s.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "DEFAULT_ANCHORS",
    "DURATION_DAYS_RAW",
    "MAX_DURATION_DAYS",
    "MAX_LOCK_AMOUNT_RAW",
    "MIN_DURATION_DAYS",
    "MIN_LOCK_AMOUNT_RAW",
    "TIER_SLATE",
    "CreditSlate",
    "InvalidDurationError",
    "PayoutAnchors",
    "TierSlateTier",
    "credit_slate_for_duration_days",
    "is_valid_lock_duration",
    "protected_amount_for",
    "trial_size_for",
    "validate_lock_duration",
]

#: Mirror of ``campaign_lock::DEFAULT_MIN_DURATION_DAYS`` / ``DEFAULT_MAX_DURATION_DAYS``.
MIN_DURATION_DAYS = 1
MAX_DURATION_DAYS = 49


@dataclass(frozen=True)
class TierSlateTier:
    """One row of the campaign's tier table (``funded_first_trade::get_tier_config``)."""

    duration_days: int
    credits: int
    tier_rank: int
    leverage: int


TIER_SLATE: tuple[TierSlateTier, ...] = (
    TierSlateTier(duration_days=1, credits=1, tier_rank=1, leverage=10),
    TierSlateTier(duration_days=4, credits=1, tier_rank=2, leverage=20),
    TierSlateTier(duration_days=7, credits=1, tier_rank=3, leverage=40),
)
"""Mirror of the compiled ``DEFAULT_TIER_*`` constants.

A lock qualifies for the highest tier with ``duration_days <=`` the lock's duration. This is a
fallback only — ``set_credit_tier_config`` can change the live table, so prefer
``Eligibility.tier_slate``.
"""

#: Compiled tier thresholds — matches :data:`TIER_SLATE`'s defaults only.
DURATION_DAYS_RAW: tuple[int, ...] = (1, 4, 7)

# Mirror of payout_math's DEFAULT_{LOW,HIGH}_{LOCK,PROTECTED} anchors.
_PAYOUT_LOW_LOCK = 250_000_000
_PAYOUT_LOW_PROTECTED = 10_000_000
_PAYOUT_HIGH_LOCK = 5_000_000_000
_PAYOUT_HIGH_PROTECTED = 220_000_000

MIN_LOCK_AMOUNT_RAW = _PAYOUT_LOW_LOCK
MAX_LOCK_AMOUNT_RAW = _PAYOUT_HIGH_LOCK


@dataclass(frozen=True)
class PayoutAnchors:
    low_lock: int
    low_protected: int
    high_lock: int
    high_protected: int


DEFAULT_ANCHORS = PayoutAnchors(
    low_lock=_PAYOUT_LOW_LOCK,
    low_protected=_PAYOUT_LOW_PROTECTED,
    high_lock=_PAYOUT_HIGH_LOCK,
    high_protected=_PAYOUT_HIGH_PROTECTED,
)


class InvalidDurationError(ValueError):
    def __init__(self, duration_days: int) -> None:
        super().__init__(
            f"duration_days {duration_days} outside [{MIN_DURATION_DAYS}, {MAX_DURATION_DAYS}]"
        )
        self.duration_days = duration_days


def is_valid_lock_duration(days: int) -> bool:
    """Non-throwing mirror of :func:`validate_lock_duration`."""
    return MIN_DURATION_DAYS <= days <= MAX_DURATION_DAYS


def validate_lock_duration(days: int) -> None:
    """Mirror of ``campaign_lock::assert_valid_duration`` at the default bounds."""
    if not is_valid_lock_duration(days):
        raise InvalidDurationError(days)


def protected_amount_for(active_locked: int, anchors: PayoutAnchors = DEFAULT_ANCHORS) -> int:
    """Mirror of ``payout_math::compute``.

    Evaluated on the user's *total* active locked principal, not per-lock.
    """
    if active_locked < anchors.low_lock:
        return 0
    if active_locked >= anchors.high_lock:
        return anchors.high_protected
    span = anchors.high_lock - anchors.low_lock
    value_range = anchors.high_protected - anchors.low_protected
    delta = active_locked - anchors.low_lock
    # Integer division, matching the Move u64 arithmetic.
    return anchors.low_protected + (value_range * delta) // span


@dataclass(frozen=True)
class CreditSlate:
    credits: int
    tier_rank: int
    leverage: int


def credit_slate_for_duration_days(
    days: int, slate: tuple[TierSlateTier, ...] | list[TierSlateTier] = TIER_SLATE
) -> CreditSlate:
    """Mirror of ``user_credits::credit_slate_for_duration_days``.

    Picks the highest tier whose ``duration_days <= days``, and zeros below the first tier. Pass
    the live slate from ``Eligibility.tier_slate``; the compiled default is a loading-state
    fallback.
    """
    result = CreditSlate(credits=0, tier_rank=0, leverage=0)
    for tier in slate:
        if days >= tier.duration_days:
            result = CreditSlate(
                credits=tier.credits, tier_rank=tier.tier_rank, leverage=tier.leverage
            )
    return result


def trial_size_for(
    active_locked: int,
    duration_days: int,
    anchors: PayoutAnchors = DEFAULT_ANCHORS,
    slate: tuple[TierSlateTier, ...] | list[TierSlateTier] = TIER_SLATE,
) -> int:
    """Per-credit trial position: ``protected_amount * leverage_at_grant``, in raw USDC.

    This is the notional ``funded_first_trade::open_trial`` reserves per trial. Pass the live
    anchors/slate from ``Eligibility``; the defaults are a fallback.
    """
    validate_lock_duration(duration_days)
    slate_row = credit_slate_for_duration_days(duration_days, slate)
    return protected_amount_for(active_locked, anchors) * slate_row.leverage
