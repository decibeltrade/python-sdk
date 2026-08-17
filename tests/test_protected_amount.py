"""Tests for the Move payout/tier math mirrors in decibel._protected_amount."""

from __future__ import annotations

import pytest

from decibel._protected_amount import (
    DEFAULT_ANCHORS,
    MAX_DURATION_DAYS,
    MAX_LOCK_AMOUNT_RAW,
    MIN_DURATION_DAYS,
    MIN_LOCK_AMOUNT_RAW,
    TIER_SLATE,
    InvalidDurationError,
    PayoutAnchors,
    TierSlateTier,
    credit_slate_for_duration_days,
    is_valid_lock_duration,
    protected_amount_for,
    trial_size_for,
    validate_lock_duration,
)


class TestLockDurationValidation:
    @pytest.mark.parametrize("days", [MIN_DURATION_DAYS, 7, 30, MAX_DURATION_DAYS])
    def test_accepts_in_range(self, days: int) -> None:
        assert is_valid_lock_duration(days) is True
        validate_lock_duration(days)

    @pytest.mark.parametrize("days", [0, -1, MAX_DURATION_DAYS + 1, 365])
    def test_rejects_out_of_range(self, days: int) -> None:
        assert is_valid_lock_duration(days) is False
        with pytest.raises(InvalidDurationError) as exc_info:
            validate_lock_duration(days)
        assert exc_info.value.duration_days == days

    def test_error_is_a_value_error(self) -> None:
        assert issubclass(InvalidDurationError, ValueError)


class TestProtectedAmountFor:
    def test_below_low_anchor_is_zero(self) -> None:
        assert protected_amount_for(MIN_LOCK_AMOUNT_RAW - 1) == 0

    def test_at_low_anchor(self) -> None:
        assert protected_amount_for(MIN_LOCK_AMOUNT_RAW) == DEFAULT_ANCHORS.low_protected

    def test_at_high_anchor(self) -> None:
        assert protected_amount_for(MAX_LOCK_AMOUNT_RAW) == DEFAULT_ANCHORS.high_protected

    def test_above_high_anchor_clamps(self) -> None:
        assert protected_amount_for(MAX_LOCK_AMOUNT_RAW * 10) == DEFAULT_ANCHORS.high_protected

    def test_midpoint_interpolates(self) -> None:
        midpoint = (MIN_LOCK_AMOUNT_RAW + MAX_LOCK_AMOUNT_RAW) // 2
        expected = DEFAULT_ANCHORS.low_protected + (
            (DEFAULT_ANCHORS.high_protected - DEFAULT_ANCHORS.low_protected)
            * (midpoint - MIN_LOCK_AMOUNT_RAW)
        ) // (MAX_LOCK_AMOUNT_RAW - MIN_LOCK_AMOUNT_RAW)
        assert protected_amount_for(midpoint) == expected

    def test_result_is_an_int(self) -> None:
        # Must stay integral: the Move side is u64 arithmetic, not floats.
        assert isinstance(protected_amount_for(1_234_567_890), int)

    def test_monotonic_in_locked_amount(self) -> None:
        step = (MAX_LOCK_AMOUNT_RAW - MIN_LOCK_AMOUNT_RAW) // 20
        amounts = [MIN_LOCK_AMOUNT_RAW + step * i for i in range(21)]
        payouts = [protected_amount_for(a) for a in amounts]
        assert payouts == sorted(payouts)

    def test_custom_anchors(self) -> None:
        anchors = PayoutAnchors(low_lock=100, low_protected=10, high_lock=200, high_protected=20)
        assert protected_amount_for(99, anchors) == 0
        assert protected_amount_for(100, anchors) == 10
        assert protected_amount_for(150, anchors) == 15
        assert protected_amount_for(200, anchors) == 20


class TestCreditSlateForDurationDays:
    def test_below_first_tier_is_zeroed(self) -> None:
        slate = credit_slate_for_duration_days(0)
        assert (slate.credits, slate.tier_rank, slate.leverage) == (0, 0, 0)

    @pytest.mark.parametrize(("days", "expected_rank"), [(1, 1), (3, 1), (4, 2), (6, 2), (7, 3)])
    def test_picks_highest_qualifying_tier(self, days: int, expected_rank: int) -> None:
        assert credit_slate_for_duration_days(days).tier_rank == expected_rank

    def test_above_last_tier_stays_on_last_tier(self) -> None:
        assert credit_slate_for_duration_days(365).tier_rank == TIER_SLATE[-1].tier_rank

    def test_custom_slate(self) -> None:
        slate = [
            TierSlateTier(duration_days=2, credits=5, tier_rank=1, leverage=3),
            TierSlateTier(duration_days=10, credits=9, tier_rank=2, leverage=8),
        ]
        assert credit_slate_for_duration_days(1, slate).credits == 0
        assert credit_slate_for_duration_days(2, slate).credits == 5
        assert credit_slate_for_duration_days(10, slate).leverage == 8


class TestTrialSizeFor:
    def test_is_protected_amount_times_leverage(self) -> None:
        locked = 1_000_000_000
        expected = protected_amount_for(locked) * credit_slate_for_duration_days(7).leverage
        assert trial_size_for(locked, 7) == expected

    def test_zero_when_below_min_lock(self) -> None:
        assert trial_size_for(MIN_LOCK_AMOUNT_RAW - 1, 7) == 0

    def test_zero_below_first_tier_even_with_a_big_lock(self) -> None:
        # duration 1 is the first tier, so pick a slate whose first tier starts later.
        slate = [TierSlateTier(duration_days=30, credits=1, tier_rank=1, leverage=10)]
        assert trial_size_for(MAX_LOCK_AMOUNT_RAW, 7, DEFAULT_ANCHORS, slate) == 0

    def test_rejects_invalid_duration(self) -> None:
        with pytest.raises(InvalidDurationError):
            trial_size_for(MAX_LOCK_AMOUNT_RAW, MAX_DURATION_DAYS + 1)


class TestTierSlateDefaults:
    def test_ascending_by_duration(self) -> None:
        durations = [tier.duration_days for tier in TIER_SLATE]
        assert durations == sorted(durations)

    def test_ranks_are_sequential(self) -> None:
        assert [tier.tier_rank for tier in TIER_SLATE] == list(range(1, len(TIER_SLATE) + 1))
