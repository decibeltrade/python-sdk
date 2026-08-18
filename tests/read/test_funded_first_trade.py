"""Tests for the funded-first-trade eligibility rules and reader wiring."""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from decibel._protected_amount import DEFAULT_ANCHORS, TIER_SLATE, protected_amount_for
from decibel.read._base import ReaderDeps
from decibel.read._funded_first_trade import (
    SOFT_BURN_WARN_RATIO,
    ActiveLock,
    DailyBurn,
    EligibilityInputs,
    FundedFirstTradeReader,
    LockTotals,
    OiState,
    ProtectedTrialUpdate,
    TrialConfig,
    UserCredits,
    compute_eligibility,
)

_MIN_LOCK = 250_000_000
_MARKET = "0xmarket"


def _inputs(**overrides: object) -> EligibilityInputs:
    """A fully-eligible baseline; override one field per test to isolate a blocker."""
    base = EligibilityInputs(
        lock_totals=LockTotals(
            active_locked_amount=1_000_000_000,
            min_active_duration_days=7,
            active_lock_count=1,
        ),
        credit_account=UserCredits(granted=1, used=0),
        trials_paused=False,
        locks_paused=False,
        all_trials_frozen=False,
        market_open=True,
        trial_config=TrialConfig(
            market_addr=_MARKET,
            min_lock_amount=_MIN_LOCK,
            expiry_ms=600_000,
            size_decimals_pow10=1_000_000,
            payout_anchors=DEFAULT_ANCHORS,
        ),
        tier_slate=list(TIER_SLATE),
        burn=DailyBurn(window_total=0, cap=10_000_000_000, live_reservation_count=0),
        oi=OiState(total_notional=0, cap=10_000_000_000),
        campaign_title="Funded First Trade",
        active_lock=ActiveLock(lock_id=1, unlocks_at_ms=1_700_000_000_000, lock_subaccount="0xsub"),
        has_active_trial=False,
        relock_disabled=False,
        has_ever_been_granted=False,
    )
    return dataclasses.replace(base, **overrides)  # type: ignore[arg-type]


class TestComputeEligibilityHappyPath:
    def test_eligible_has_no_blockers(self) -> None:
        result = compute_eligibility(_inputs())
        assert result.can_open_trial is True
        assert result.blockers == []
        assert result.blocker_codes == []

    def test_passes_through_config_and_totals(self) -> None:
        result = compute_eligibility(_inputs())
        assert result.market_addr == _MARKET
        assert result.min_lock_amount == _MIN_LOCK
        assert result.expiry_ms == 600_000
        assert result.campaign_title == "Funded First Trade"
        assert result.active_locked_amount == 1_000_000_000
        assert result.credits_granted == 1
        assert result.credits_used == 0

    def test_active_lock_fields_are_flattened(self) -> None:
        result = compute_eligibility(_inputs())
        assert result.active_lock_id == 1
        assert result.active_lock_unlock_at_ms == 1_700_000_000_000
        assert result.active_lock_subaccount == "0xsub"

    def test_no_active_lock_nulls_the_lock_fields(self) -> None:
        result = compute_eligibility(_inputs(active_lock=None))
        assert result.active_lock_id is None
        assert result.active_lock_unlock_at_ms is None
        assert result.active_lock_subaccount is None

    def test_projected_burn_adds_this_users_protected_amount(self) -> None:
        result = compute_eligibility(_inputs())
        assert result.daily_burn.projected_after_trial == protected_amount_for(1_000_000_000)


class TestComputeEligibilityBlockers:
    @pytest.mark.parametrize(
        ("overrides", "code"),
        [
            ({"trials_paused": True}, "trials_paused"),
            ({"all_trials_frozen": True}, "trials_frozen"),
            ({"market_open": False}, "market_not_open"),
            ({"has_active_trial": True}, "trial_already_active"),
            ({"credit_account": UserCredits(granted=1, used=1)}, "no_credits"),
            (
                {
                    "lock_totals": LockTotals(
                        active_locked_amount=_MIN_LOCK - 1,
                        min_active_duration_days=7,
                        active_lock_count=1,
                    )
                },
                "below_min_lock",
            ),
            (
                {"burn": DailyBurn(window_total=0, cap=1, live_reservation_count=0)},
                "daily_budget_exhausted",
            ),
            ({"oi": OiState(total_notional=10, cap=10)}, "oi_cap_reached"),
        ],
    )
    def test_each_blocker_fires(self, overrides: dict[str, object], code: str) -> None:
        result = compute_eligibility(_inputs(**overrides))
        assert result.can_open_trial is False
        assert code in result.blocker_codes

    def test_blockers_and_codes_stay_parallel(self) -> None:
        result = compute_eligibility(_inputs(trials_paused=True, market_open=False))
        assert len(result.blockers) == len(result.blocker_codes) == 2
        assert result.blocker_codes == ["trials_paused", "market_not_open"]

    def test_locks_paused_alone_does_not_block_opening(self) -> None:
        # locks_paused gates *locking*, not opening a trial against an existing lock.
        result = compute_eligibility(_inputs(locks_paused=True))
        assert result.can_open_trial is True
        assert result.locks_paused is True

    def test_used_credits_exceeding_granted_blocks(self) -> None:
        result = compute_eligibility(_inputs(credit_account=UserCredits(granted=1, used=5)))
        assert "no_credits" in result.blocker_codes

    def test_oi_below_cap_does_not_block(self) -> None:
        result = compute_eligibility(_inputs(oi=OiState(total_notional=9, cap=10)))
        assert "oi_cap_reached" not in result.blocker_codes


class TestSoftWarnings:
    def test_warns_past_the_soft_ratio(self) -> None:
        projected = protected_amount_for(1_000_000_000)
        # Cap just low enough that projected lands above 70% of it.
        cap = int(projected / SOFT_BURN_WARN_RATIO) - 1_000
        result = compute_eligibility(
            _inputs(burn=DailyBurn(window_total=0, cap=cap, live_reservation_count=0))
        )
        assert result.soft_warnings.daily_burn_near_cap is True

    def test_quiet_well_below_the_soft_ratio(self) -> None:
        result = compute_eligibility(
            _inputs(burn=DailyBurn(window_total=0, cap=1_000_000_000_000, live_reservation_count=0))
        )
        assert result.soft_warnings.daily_burn_near_cap is False


@pytest.fixture
def reader_deps(test_config: object) -> ReaderDeps:
    return ReaderDeps(
        config=test_config,  # type: ignore[arg-type]
        ws=MagicMock(),
        aptos=MagicMock(),
        api_key="test-key",
        http_client=AsyncMock(spec=httpx.AsyncClient),
        http_client_sync=MagicMock(spec=httpx.Client),
    )


class TestFundedFirstTradeReader:
    def test_subscribe_by_addr_topic(self, reader_deps: ReaderDeps) -> None:
        reader = FundedFirstTradeReader(reader_deps)
        reader_deps.ws.subscribe.return_value = MagicMock()

        reader.subscribe_by_addr("0xuser", MagicMock())

        args = reader_deps.ws.subscribe.call_args[0]
        assert args[0] == "protected_trial_update:0xuser"
        assert args[1] is ProtectedTrialUpdate

    def test_missing_campaign_package_raises(self, reader_deps: ReaderDeps) -> None:
        deployment = dataclasses.replace(reader_deps.config.deployment, campaign_package="")
        deps = dataclasses.replace(
            reader_deps, config=dataclasses.replace(reader_deps.config, deployment=deployment)
        )
        reader = FundedFirstTradeReader(deps)

        with pytest.raises(ValueError, match="no campaign package"):
            _ = reader._campaign_package


class TestFindActiveLockFromChain:
    """The on-chain lock scan is already the degraded path — one bad entry must not sink it."""

    def _reader(self, reader_deps: ReaderDeps, locks: dict[int, object]) -> FundedFirstTradeReader:
        # The shared fixture deployment has no campaign package; the scan needs one.
        config = dataclasses.replace(
            reader_deps.config,
            deployment=dataclasses.replace(
                reader_deps.config.deployment, campaign_package="0xcampaign"
            ),
        )
        reader = FundedFirstTradeReader(dataclasses.replace(reader_deps, config=config))

        async def campaign_view(module: str, fn: str, arguments: list[object]) -> list[object]:
            if fn == "next_lock_id":
                return [str(len(locks))]
            lock_id = int(arguments[1])
            if fn == "is_lock_active":
                return [True]
            if fn == "get_lock":
                value = locks[lock_id]
                if isinstance(value, Exception):
                    raise value
                return [value]
            raise AssertionError(f"unexpected view {fn}")

        reader._campaign_view = campaign_view  # type: ignore[assignment,method-assign]
        return reader

    def _lock(self, user: str) -> dict[str, object]:
        return {
            "user": user,
            "unlocks_at_ms": "1700000000000",
            "lock_subaccount": {"inner": "0xsub"},
        }

    async def test_finds_the_owners_lock(self, reader_deps: ReaderDeps) -> None:
        reader = self._reader(reader_deps, {0: self._lock("0xaaa"), 1: self._lock("0xbbb")})

        found = await reader.find_active_lock_from_chain("0xbbb")

        assert found is not None
        assert found.lock_id == 1

    async def test_malformed_lock_is_skipped_not_fatal(self, reader_deps: ReaderDeps) -> None:
        # A struct missing `user` (e.g. after a contract upgrade) used to raise out of the scan
        # because the parse sat outside the try.
        reader = self._reader(
            reader_deps,
            {
                0: {"unlocks_at_ms": "1", "lock_subaccount": {"inner": "0x1"}},
                1: self._lock("0xbbb"),
            },
        )

        found = await reader.find_active_lock_from_chain("0xbbb")

        assert found is not None
        assert found.lock_id == 1

    async def test_view_error_is_skipped(self, reader_deps: ReaderDeps) -> None:
        reader = self._reader(
            reader_deps, {0: RuntimeError("rate limited"), 1: self._lock("0xbbb")}
        )

        found = await reader.find_active_lock_from_chain("0xbbb")

        assert found is not None
        assert found.lock_id == 1
