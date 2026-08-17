from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from aptos_sdk.account_address import AccountAddress
from pydantic import BaseModel, ConfigDict

from .._protected_amount import PayoutAnchors, TierSlateTier, protected_amount_for
from ._base import BaseReader

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ._base import ReaderDeps
    from ._ws import Unsubscribe

__all__ = [
    "SOFT_BURN_WARN_RATIO",
    "ActiveLock",
    "CampaignLocksResponse",
    "DailyBurn",
    "Eligibility",
    "EligibilityInputs",
    "FftBlockerCode",
    "FundedFirstTradeReader",
    "LockDto",
    "LockStatus",
    "LockTotals",
    "OiState",
    "ProtectedTrialUpdate",
    "ProtectedTrialsResponse",
    "SettleReason",
    "SoftWarnings",
    "TradeSide",
    "TrialConfig",
    "TrialDto",
    "TrialHistoryPage",
    "TrialPriorStatus",
    "TrialStatus",
    "UserCredits",
    "compute_eligibility",
]

_LOG = logging.getLogger(__name__)

# A trial that settled within this window is still worth showing as "the current trial", so the
# UI can render the outcome instead of snapping back to an empty state.
_RECENT_SETTLE_WINDOW_MS = 5 * 60 * 1000

#: Warn before the daily-burn hard cap: surfaces a banner once projected burn passes this
#: fraction of the cap.
SOFT_BURN_WARN_RATIO = 0.7
_SOFT_BURN_WARN_NUMERATOR = 7
_SOFT_BURN_WARN_DENOMINATOR = 10

# No per-owner lock-id view exists on-chain, so the fallback walks `0..next_lock_id`. Past this
# many locks the scan gives up rather than hammering the fullnode.
_LOCK_SCAN_CAP = 200

# Wire-shape enums (the Rust serde default is PascalCase).

TradeSide = Literal["Buy", "Sell"]

TrialStatus = Literal["Active", "Settled", "SettledLiquidated"]

SettleReason = Literal[
    "ExpiredClean",
    "LiquidatedEmpty",
    "PartialLoss",
    "NeverFilled",
    "AdminForced",
    "SweptAfterStall",
    "AdminReset",
]

TrialPriorStatus = Literal["Active"]
"""Resets are only allowed from on-chain Opening/Open, both of which collapse to ``Active``."""

LockStatus = Literal["Active", "Claimed"]


class TrialDto(BaseModel):
    """Trial row from ``/api/v1/protected_trials`` and ``protected_trial_update:{addr}``.

    Presence matrix: the open-sourced fields are absent only on degraded reset rows (an
    enrichment miss, over either transport); the terminal fields appear on closed/reset rows only.
    """

    model_config = ConfigDict(populate_by_name=True)

    trial_id: int
    user: str
    campaign_addr: str
    status: TrialStatus
    #: Normalized size (``market.normalize_size`` float). Always serialized; ``None`` when the
    #: market is unknown.
    size: float | None

    market: str | None = None
    trial_subaccount: str | None = None
    side: TradeSide | None = None
    protected_amount: int | None = None
    protected_amount_usd: float | None = None
    mark_at_open: int | None = None
    mark_at_open_usd: float | None = None
    leverage_at_open: int | None = None
    mark_at_close: int | None = None
    mark_at_close_usd: float | None = None
    opened_at_ms: int | None = None
    expires_at_ms: int | None = None

    closed_at_ms: int | None = None
    vault_returned: int | None = None
    vault_returned_usd: float | None = None
    user_payout: int | None = None
    user_payout_usd: float | None = None
    settle_reason: SettleReason | None = None
    closed_by: str | None = None
    prior_status: TrialPriorStatus | None = None
    close_stalled: bool | None = None


class ProtectedTrialsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    active_trial: TrialDto | None
    active_trials: list[TrialDto]
    history: list[TrialDto]
    #: SQL-level count — server-skipped rows still count, so never assert
    #: ``len(history) == history_total_count`` on the last page.
    history_total_count: int


class LockDto(BaseModel):
    """A campaign lock. Extension fields appear on extended locks only; the returned/claimed
    fields on claimed locks only."""

    model_config = ConfigDict(populate_by_name=True)

    lock_id: int
    campaign_addr: str
    trial_id: int
    amount: int
    amount_usd: float
    duration_days: int
    lock_subaccount: str
    locked_at_ms: int
    unlocks_at_ms: int
    status: LockStatus
    was_extended: bool
    previous_unlocks_at_ms: int | None = None
    extended_at_ms: int | None = None
    #: Trading-PnL-adjusted, so it may differ from ``amount``.
    returned_amount: int | None = None
    returned_amount_usd: float | None = None
    claimed_at_ms: int | None = None


class CampaignLocksResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account: str
    locks: list[LockDto]
    #: Skipped orphan rows still count and consume page slots, so
    #: ``has_next_page = offset + limit < total_count``.
    total_count: int


class ProtectedTrialUpdate(BaseModel):
    """WS payload; matches the ``trials`` field of the Rust ``ProtectedTrialUpdateResponse``."""

    model_config = ConfigDict(populate_by_name=True)

    trials: list[TrialDto]


@dataclass(frozen=True)
class TrialHistoryPage:
    history: list[TrialDto]
    #: SQL-level total for "X of N"; may exceed the rows returned across all pages, because the
    #: server skips some.
    history_total_count: int


FftBlockerCode = Literal[
    "trials_paused",
    "trials_frozen",
    "market_not_open",
    "trial_already_active",
    "no_credits",
    "below_min_lock",
    "daily_budget_exhausted",
    "oi_cap_reached",
]
"""Stable machine codes for :attr:`Eligibility.blockers` — safe for analytics/segmentation
(the copy may change; the codes may not)."""


@dataclass(frozen=True)
class LockTotals:
    #: Raw USDC.
    active_locked_amount: int
    min_active_duration_days: int
    active_lock_count: int


@dataclass(frozen=True)
class UserCredits:
    granted: int
    used: int


@dataclass(frozen=True)
class TrialConfig:
    market_addr: str
    #: Raw USDC.
    min_lock_amount: int
    expiry_ms: int
    size_decimals_pow10: int
    payout_anchors: PayoutAnchors


@dataclass(frozen=True)
class DailyBurn:
    window_total: int
    cap: int
    live_reservation_count: int
    #: ``window_total`` plus this user's projected protected amount if they open now.
    projected_after_trial: int = 0


@dataclass(frozen=True)
class OiState:
    """Single total open-interest meter."""

    total_notional: int
    cap: int


@dataclass(frozen=True)
class ActiveLock:
    lock_id: int
    unlocks_at_ms: int
    lock_subaccount: str


@dataclass(frozen=True)
class SoftWarnings:
    #: Burn is past :data:`SOFT_BURN_WARN_RATIO` of the cap.
    daily_burn_near_cap: bool


@dataclass(frozen=True)
class Eligibility:
    """Composed on-chain view snapshot (not a wire shape).

    Side-agnostic: the trial side is chosen on-chain.
    """

    #: Raw USDC.
    active_locked_amount: int
    #: The active lock's duration (there is a single-lock cap on-chain).
    max_active_duration_days: int
    credits_granted: int
    credits_used: int
    active_lock_count: int

    #: ``None`` when there is no active lock, or when the bounded lock scan gave up.
    active_lock_unlock_at_ms: int | None
    active_lock_id: int | None
    #: Campaign-owned subaccount holding the locked USDC; ``None`` when no active lock was found.
    active_lock_subaccount: str | None

    #: On-chain campaign title, for labelling user-facing surfaces.
    campaign_title: str | None

    #: Raw USDC.
    min_lock_amount: int
    #: Milliseconds.
    expiry_ms: int

    #: Live payout curve; may differ from the compiled defaults via ``set_payout_config``.
    payout_anchors: PayoutAnchors
    #: Live tier table, ascending by duration; may differ from the compiled defaults via
    #: ``set_credit_tier_config``.
    tier_slate: list[TierSlateTier]

    trials_paused: bool
    locks_paused: bool
    all_trials_frozen: bool

    daily_burn: DailyBurn
    oi_state: OiState

    #: The perp market address the campaign uses for trials.
    market_addr: str

    can_open_trial: bool
    #: Human-readable reasons ``can_open_trial`` is false; empty when openable.
    blockers: list[str]
    #: Parallel to :attr:`blockers`, same order.
    blocker_codes: list[FftBlockerCode]

    #: On-chain ``relock_disabled``: when true, users with prior credits cannot lock again.
    relock_disabled: bool
    #: On-chain ``has_ever_been_granted``: true if the user received credits from a prior lock.
    has_ever_been_granted: bool

    soft_warnings: SoftWarnings


@dataclass(frozen=True)
class EligibilityInputs:
    lock_totals: LockTotals
    credit_account: UserCredits
    trials_paused: bool
    locks_paused: bool
    all_trials_frozen: bool
    #: Best-effort: mode views are a cache, so a market can read Open with a dead oracle until
    #: the first match contact.
    market_open: bool
    trial_config: TrialConfig
    tier_slate: list[TierSlateTier]
    burn: DailyBurn
    oi: OiState
    campaign_title: str | None
    active_lock: ActiveLock | None
    has_active_trial: bool
    relock_disabled: bool
    has_ever_been_granted: bool


def compute_eligibility(inputs: EligibilityInputs) -> Eligibility:
    """Fold the on-chain campaign views into a single :class:`Eligibility` snapshot.

    The gating here is UX sugar — the authoritative rules fire in the ``open_trial`` entry
    function, so treat a stale ``can_open_trial`` as a race to re-fetch, not a guarantee.
    """
    # payout_math.compute gates on total active locked principal alone; no active lock -> 0.
    projected_trial_amount = protected_amount_for(
        inputs.lock_totals.active_locked_amount, inputs.trial_config.payout_anchors
    )
    projected_after_trial = inputs.burn.window_total + projected_trial_amount

    blockers: list[str] = []
    blocker_codes: list[FftBlockerCode] = []

    def block(code: FftBlockerCode, message: str) -> None:
        blockers.append(message)
        blocker_codes.append(code)

    if inputs.trials_paused:
        block("trials_paused", "Trials are paused")
    if inputs.all_trials_frozen:
        block("trials_frozen", "Trials are temporarily frozen by ops")
    # Opening on a closed market never aborts on-chain — the IOC is engine-cancelled, the credit
    # burns, and the trial settles NeverFilled. This gate is the only defence.
    if not inputs.market_open:
        block("market_not_open", "The trial market is temporarily closed — try again later")
    if inputs.has_active_trial:
        block("trial_already_active", "Finish your active trial before opening another")
    if inputs.credit_account.granted - inputs.credit_account.used <= 0:
        block("no_credits", "No trial credits available — lock more USDC to earn credits")
    if inputs.lock_totals.active_locked_amount < inputs.trial_config.min_lock_amount:
        block("below_min_lock", "Lock amount is below the minimum required to open a trial")
    if projected_after_trial > inputs.burn.cap:
        block("daily_budget_exhausted", "Daily campaign budget is exhausted — try again tomorrow")
    if inputs.oi.total_notional >= inputs.oi.cap:
        block("oi_cap_reached", "Open-interest cap reached — come back later")

    soft_cap = (_SOFT_BURN_WARN_NUMERATOR * inputs.burn.cap) // _SOFT_BURN_WARN_DENOMINATOR

    return Eligibility(
        active_locked_amount=inputs.lock_totals.active_locked_amount,
        # Single-lock cap on-chain: the owner's min active duration IS the lock's duration.
        max_active_duration_days=inputs.lock_totals.min_active_duration_days,
        credits_granted=inputs.credit_account.granted,
        credits_used=inputs.credit_account.used,
        active_lock_count=inputs.lock_totals.active_lock_count,
        active_lock_unlock_at_ms=(
            inputs.active_lock.unlocks_at_ms if inputs.active_lock is not None else None
        ),
        active_lock_id=inputs.active_lock.lock_id if inputs.active_lock is not None else None,
        active_lock_subaccount=(
            inputs.active_lock.lock_subaccount if inputs.active_lock is not None else None
        ),
        campaign_title=inputs.campaign_title,
        min_lock_amount=inputs.trial_config.min_lock_amount,
        expiry_ms=inputs.trial_config.expiry_ms,
        payout_anchors=inputs.trial_config.payout_anchors,
        tier_slate=inputs.tier_slate,
        trials_paused=inputs.trials_paused,
        locks_paused=inputs.locks_paused,
        all_trials_frozen=inputs.all_trials_frozen,
        daily_burn=DailyBurn(
            window_total=inputs.burn.window_total,
            cap=inputs.burn.cap,
            live_reservation_count=inputs.burn.live_reservation_count,
            projected_after_trial=projected_after_trial,
        ),
        oi_state=inputs.oi,
        market_addr=inputs.trial_config.market_addr,
        can_open_trial=not blockers,
        blockers=blockers,
        blocker_codes=blocker_codes,
        relock_disabled=inputs.relock_disabled,
        has_ever_been_granted=inputs.has_ever_been_granted,
        soft_warnings=SoftWarnings(daily_burn_near_cap=projected_after_trial > soft_cap),
    )


def _inner(value: Any) -> str:
    """Unwrap a Move ``Object<T>`` view result (``{"inner": "0x..."}``)."""
    if isinstance(value, dict):
        return str(cast("dict[str, Any]", value)["inner"])
    return str(value)


def _trial_dto_from_chain(
    data: dict[str, Any],
    *,
    user: str,
    campaign_addr: str,
    market: str,
    size_scale: float,
    status: TrialStatus,
) -> TrialDto:
    protected_amount = int(data["protected_amount"])
    mark_at_open = int(data["mark_at_open"])
    return TrialDto(
        trial_id=int(data["trial_id"]),
        user=user,
        campaign_addr=campaign_addr,
        market=market,
        side="Buy" if data.get("side_is_buy") is True else "Sell",
        protected_amount=protected_amount,
        protected_amount_usd=protected_amount / 1_000_000,
        size=float(data["size"]) * size_scale,
        mark_at_open=mark_at_open,
        mark_at_open_usd=mark_at_open / 1_000_000,
        trial_subaccount=str(data["trial_subaccount"]),
        opened_at_ms=int(data["opened_at_ms"]),
        expires_at_ms=int(data["expires_at_ms"]),
        status=status,
    )


class FundedFirstTradeReader(BaseReader):
    """Reader for Funded First Trade (FFT).

    Composes the on-chain campaign views into :class:`Eligibility`, and serves trials via
    ``/api/v1/protected_trials`` plus the ``protected_trial_update:{addr}`` WS topic.
    """

    def __init__(self, deps: ReaderDeps) -> None:
        super().__init__(deps)
        self._warned_fallbacks: set[str] = set()

    @property
    def _campaign_package(self) -> str:
        """Module address — where the ``funded_first_trade`` family of modules lives."""
        package = self.config.deployment.campaign_package
        if not package:
            raise ValueError(
                "This deployment has no campaign package configured; "
                "set Deployment.campaign_package to use the funded-first-trade reader"
            )
        return package

    @property
    def _campaign_addr(self) -> str:
        """Campaign *object* address (the ``create_campaign`` result).

        This is what every ``campaign_addr`` argument takes — distinct from the package address,
        which it falls back to only for configs that predate the split.
        """
        return self.config.deployment.fft_campaign_addr or self._campaign_package

    def _note_chain_fallback(self, method: str, error: Exception) -> None:
        """Log the first fall-back per method.

        Without this the rebuild masks API regressions: a 200 with a drifted wire shape fails
        validation and lands here just like an outage. Latched per method because the settling
        poll retries every few seconds and would otherwise flood the logs.
        """
        if method in self._warned_fallbacks:
            return
        self._warned_fallbacks.add(method)
        _LOG.warning(
            "FFT: trading-api request failed, rebuilding from chain views (method=%s)",
            method,
            exc_info=error,
        )

    async def get_eligibility(self, account: str) -> Eligibility:
        """Snapshot of whether ``account`` can open a trial right now, and why not if it can't."""
        campaign = self._campaign_addr
        # A TaskGroup rather than asyncio.gather: with this many heterogeneous results, gather
        # collapses them to a single union type and every downstream field needs a cast.
        async with asyncio.TaskGroup() as tg:
            lock_totals_t = tg.create_task(self._view_owner_lock_totals(campaign, account))
            credit_account_t = tg.create_task(self._view_credit_account(campaign, account))
            trials_paused_t = tg.create_task(
                self._view_bool("protected_trial", "trials_paused", campaign)
            )
            locks_paused_t = tg.create_task(
                self._view_bool("campaign_lock", "locks_paused", campaign)
            )
            all_trials_frozen_t = tg.create_task(
                self._view_bool("protected_trial", "all_trials_frozen", campaign)
            )
            trial_config_t = tg.create_task(self._view_trial_state_config(campaign))
            tier_slate_t = tg.create_task(self._view_tier_slate(campaign))
            burn_t = tg.create_task(self._view_daily_burn(campaign))
            oi_t = tg.create_task(self._view_oi_state(campaign))
            campaign_title_t = tg.create_task(self._view_campaign_title(campaign))
            has_active_trial_t = tg.create_task(self._view_has_active_trial(campaign, account))
            relock_disabled_t = tg.create_task(
                self._view_bool("funded_first_trade", "relock_disabled", campaign)
            )
            has_ever_been_granted_t = tg.create_task(
                self._view_has_ever_been_granted(campaign, account)
            )

        lock_totals = lock_totals_t.result()
        trial_config = trial_config_t.result()

        async with asyncio.TaskGroup() as tg:
            market_open_t = tg.create_task(self._view_is_market_open(trial_config.market_addr))
            active_lock_t = (
                tg.create_task(self._find_active_lock(account))
                if lock_totals.active_lock_count > 0
                else None
            )

        return compute_eligibility(
            EligibilityInputs(
                lock_totals=lock_totals,
                credit_account=credit_account_t.result(),
                trials_paused=trials_paused_t.result(),
                locks_paused=locks_paused_t.result(),
                all_trials_frozen=all_trials_frozen_t.result(),
                market_open=market_open_t.result(),
                trial_config=trial_config,
                tier_slate=tier_slate_t.result(),
                burn=burn_t.result(),
                oi=oi_t.result(),
                campaign_title=campaign_title_t.result(),
                active_lock=active_lock_t.result() if active_lock_t is not None else None,
                has_active_trial=has_active_trial_t.result(),
                relock_disabled=relock_disabled_t.result(),
                has_ever_been_granted=has_ever_been_granted_t.result(),
            )
        )

    async def get_active_trial(self, account: str) -> TrialDto | None:
        """The account's live trial, or the one that settled in the last five minutes.

        Falls back to on-chain views when the trading API has no FFT endpoints yet, so throwaway
        deploys still work end to end.
        """
        try:
            response, _, _ = await self.get_request(
                model=ProtectedTrialsResponse,
                url=f"{self.config.trading_http_url}/api/v1/protected_trials",
                params={
                    "account": account,
                    "campaign_addr": self._campaign_addr,
                    "limit": "1",
                    "offset": "0",
                },
            )
        except Exception as error:  # noqa: BLE001 - any transport/shape failure falls back
            self._note_chain_fallback("get_active_trial", error)
            return await self.get_active_trial_from_chain(account)

        if response.active_trial is not None:
            return response.active_trial
        now_ms = time.time() * 1000
        for trial in response.history:
            if trial.campaign_addr != self._campaign_addr:
                continue
            if (
                trial.status != "Active"
                and trial.closed_at_ms is not None
                and now_ms - trial.closed_at_ms < _RECENT_SETTLE_WINDOW_MS
            ):
                return trial
            break
        return None

    async def get_trial_history(
        self, *, account: str, limit: int | None = None, offset: int | None = None
    ) -> TrialHistoryPage:
        """Settled trials for an account.

        Never raises: an empty page beats erroring out a whole dashboard. Unlike the TypeScript
        SDK there is no on-chain rebuild here — settled trials leave the on-chain map, so the
        rebuild needs an events/indexer query that this SDK has no client for.
        """
        params: dict[str, str] = {"account": account}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        try:
            response, _, _ = await self.get_request(
                model=ProtectedTrialsResponse,
                url=f"{self.config.trading_http_url}/api/v1/protected_trials",
                params=params,
            )
        except Exception as error:  # noqa: BLE001 - see docstring
            self._note_chain_fallback("get_trial_history", error)
            return TrialHistoryPage(history=[], history_total_count=0)
        return TrialHistoryPage(
            history=response.history, history_total_count=response.history_total_count
        )

    async def get_campaign_locks(
        self,
        *,
        account: str,
        campaign_addr: str | None = None,
        status: LockStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> CampaignLocksResponse:
        """The account's campaign locks. No chain fallback — this endpoint ships with the
        feature. The server default for ``limit`` is 10."""
        params: dict[str, str] = {"account": account}
        if campaign_addr is not None:
            params["campaign_addr"] = campaign_addr
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        response, _, _ = await self.get_request(
            model=CampaignLocksResponse,
            url=f"{self.config.trading_http_url}/api/v1/campaign_locks",
            params=params,
        )
        return response

    def subscribe_by_addr(
        self,
        account: str,
        on_data: (
            Callable[[ProtectedTrialUpdate], None]
            | Callable[[ProtectedTrialUpdate], Awaitable[None]]
        ),
    ) -> Unsubscribe:
        """Subscribe to ``protected_trial_update:{account}``.

        Streaming-only — fires on TrialOpened / TrialClosed / TrialResetByAdmin. Merge into the
        HTTP-seeded list by ``trial_id``. Terminal pushes may omit the open-sourced fields
        (``mark_at_open``, ``market``, …); see :class:`TrialDto`.
        """
        topic = f"protected_trial_update:{account}"
        return self.ws.subscribe(topic, ProtectedTrialUpdate, on_data)

    # ── Chain fallbacks ───────────────────────────────────────────────────────

    async def get_active_trial_from_chain(self, account: str) -> TrialDto | None:
        """Rebuild the active trial from views. Every live on-chain status maps to ``Active``,
        and ``size`` is normalized to the DTO's float convention."""
        campaign = self._campaign_addr
        id_opt = await self._campaign_view(
            "protected_trial", "active_trial_id_for", [campaign, account]
        )
        vec = id_opt[0].get("vec", [])
        if not vec:
            return None
        trial_id = str(vec[0])

        snap_result, config = await asyncio.gather(
            self._campaign_view("protected_trial", "trial_summary", [campaign, trial_id]),
            self._view_trial_state_config(campaign),
        )
        snap: dict[str, Any] = snap_result[0]
        dto = _trial_dto_from_chain(
            snap,
            user=account,
            campaign_addr=campaign,
            market=config.market_addr,
            size_scale=1 / config.size_decimals_pow10,
            status="Active",
        )
        # Closing == 2 on-chain; surfacing it lets the UI show "settling" rather than a stuck
        # open position.
        if int(snap.get("status_u8", 0)) == 2:
            dto = dto.model_copy(update={"close_stalled": True})
        return dto

    async def find_active_lock_from_chain(self, account: str) -> ActiveLock | None:
        """Owner-lock scan fallback for deploys without ``/campaign_locks``, or for indexer lag
        on a just-created lock. Returns ``None`` once the scan passes its cap."""
        campaign = self._campaign_addr
        next_id_raw = await self._campaign_view("campaign_lock", "next_lock_id", [campaign])
        next_id = int(next_id_raw[0])
        if next_id < 1 or next_id > _LOCK_SCAN_CAP:
            return None

        ids = list(range(next_id))
        active_flags = await asyncio.gather(
            *(self._view_is_lock_active(campaign, lock_id) for lock_id in ids)
        )
        owner = AccountAddress.from_str_relaxed(account)
        for lock_id, is_active in zip(ids, active_flags, strict=True):
            if not is_active:
                continue
            lock = await self._view_get_lock(campaign, lock_id)
            if lock is None:
                continue
            user, unlocks_at_ms, lock_subaccount = lock
            if AccountAddress.from_str_relaxed(user) == owner:
                return ActiveLock(
                    lock_id=lock_id,
                    unlocks_at_ms=unlocks_at_ms,
                    lock_subaccount=lock_subaccount,
                )
        return None

    async def _find_active_lock(self, account: str) -> ActiveLock | None:
        """Active lock via ``/campaign_locks``, with a chain scan behind it for missing endpoints
        (throwaway deploys) or indexer lag on a just-created lock."""
        try:
            locks = (
                await self.get_campaign_locks(
                    account=account,
                    campaign_addr=self._campaign_addr,
                    status="Active",
                    limit=1,
                )
            ).locks
            if locks:
                lock = locks[0]
                return ActiveLock(
                    lock_id=lock.lock_id,
                    unlocks_at_ms=lock.unlocks_at_ms,
                    lock_subaccount=lock.lock_subaccount,
                )
        except Exception as error:  # noqa: BLE001 - fall through to the chain scan
            self._note_chain_fallback("find_active_lock", error)
        return await self.find_active_lock_from_chain(account)

    # ── View helpers ──────────────────────────────────────────────────────────

    async def _view(self, function: str, arguments: list[Any]) -> list[Any]:
        result_bytes = await self.aptos.view(function, [], arguments)
        result: list[Any] = json.loads(result_bytes.decode("utf-8"))
        return result

    async def _campaign_view(self, module: str, fn: str, arguments: list[Any]) -> list[Any]:
        return await self._view(f"{self._campaign_package}::{module}::{fn}", arguments)

    async def _view_bool(self, module: str, fn: str, campaign: str) -> bool:
        result = await self._campaign_view(module, fn, [campaign])
        return bool(result[0])

    async def _view_has_active_trial(self, campaign: str, user: str) -> bool:
        result = await self._campaign_view(
            "protected_trial", "active_trial_id_for", [campaign, user]
        )
        return bool(result[0].get("vec"))

    async def _view_campaign_title(self, campaign: str) -> str | None:
        try:
            result = await self._campaign_view("campaign_manager", "get_campaign", [campaign])
        except Exception:  # noqa: BLE001 - a missing title is not worth failing eligibility over
            return None
        title = result[0].get("title")
        return title if isinstance(title, str) and title else None

    async def _view_owner_lock_totals(self, campaign: str, user: str) -> LockTotals:
        # (active_locked_amount: u64, min_active_duration_days: u16, active_lock_count: u64)
        result = await self._campaign_view(
            "campaign_lock", "get_owner_lock_totals", [campaign, user]
        )
        return LockTotals(
            active_locked_amount=int(result[0]),
            min_active_duration_days=int(result[1]),
            active_lock_count=int(result[2]),
        )

    async def _view_credit_account(self, campaign: str, user: str) -> UserCredits:
        # (granted: u8, used: u8, tier_rank: u8, slate_version: u32)
        result = await self._campaign_view("user_credits", "get_credit_account", [campaign, user])
        return UserCredits(granted=int(result[0]), used=int(result[1]))

    async def _view_trial_state_config(self, campaign: str) -> TrialConfig:
        result = await self._campaign_view("protected_trial", "trial_state_config", [campaign])
        config: dict[str, Any] = result[0]
        return TrialConfig(
            market_addr=_inner(config["market"]),
            expiry_ms=int(config["expiry_ms"]),
            min_lock_amount=int(config["min_lock_amount"]),
            size_decimals_pow10=int(config["size_decimals_pow10"]),
            payout_anchors=PayoutAnchors(
                low_lock=int(config["payout_low_lock"]),
                low_protected=int(config["payout_low_protected"]),
                high_lock=int(config["payout_high_lock"]),
                high_protected=int(config["payout_high_protected"]),
            ),
        )

    async def _view_tier_slate(self, campaign: str) -> list[TierSlateTier]:
        result = await self._campaign_view("funded_first_trade", "get_tier_config", [campaign])
        # Enum view: `{"__variant__": "V1", "tier_config_version": .., "tiers": [..]}`;
        # the u64 leverage arrives as a string.
        tiers: list[dict[str, Any]] = result[0]["tiers"]
        return [
            TierSlateTier(
                duration_days=int(tier["duration_days"]),
                credits=int(tier["credits"]),
                tier_rank=int(tier["tier_rank"]),
                leverage=int(tier["leverage"]),
            )
            for tier in tiers
        ]

    async def _view_is_market_open(self, market_addr: str) -> bool:
        """``perp_engine`` view — the dex package, not the campaign package.

        Fails open: the probe is UX gating, and the engine's own order cancel is the
        authoritative rejection.
        """
        try:
            result = await self._view(
                f"{self.config.deployment.package}::perp_engine::is_market_open", [market_addr]
            )
        except Exception:  # noqa: BLE001 - see docstring
            return True
        return bool(result[0])

    async def _view_daily_burn(self, campaign: str) -> DailyBurn:
        result = await self._campaign_view("protected_trial", "daily_burn_view", [campaign])
        burn: dict[str, Any] = result[0]
        return DailyBurn(
            cap=int(burn["cap_usd"]),
            window_total=int(burn["window_total_usd"]),
            live_reservation_count=int(burn["live_reservation_count"]),
        )

    async def _view_oi_state(self, campaign: str) -> OiState:
        result = await self._campaign_view("protected_trial", "oi_state", [campaign])
        oi: dict[str, Any] = result[0]
        return OiState(total_notional=int(oi["total_notional"]), cap=int(oi["cap"]))

    async def _view_has_ever_been_granted(self, campaign: str, user: str) -> bool:
        result = await self._campaign_view(
            "user_credits", "has_ever_been_granted", [campaign, user]
        )
        return bool(result[0])

    async def _view_is_lock_active(self, campaign: str, lock_id: int) -> bool:
        try:
            result = await self._campaign_view(
                "campaign_lock", "is_lock_active", [campaign, str(lock_id)]
            )
        except Exception:  # noqa: BLE001 - a gap in the id range is not an error
            return False
        return bool(result[0])

    async def _view_get_lock(self, campaign: str, lock_id: int) -> tuple[str, int, str] | None:
        try:
            result = await self._campaign_view(
                "campaign_lock", "get_lock", [campaign, str(lock_id)]
            )
            lock: dict[str, Any] = result[0]
            return (
                str(lock["user"]),
                int(lock["unlocks_at_ms"]),
                _inner(lock["lock_subaccount"]),
            )
        except Exception:  # noqa: BLE001 - a gap in the id range, or a struct we can't read,
            # skips that lock rather than aborting the whole scan. This is already the
            # degraded path, so one unreadable entry must not sink the rest.
            return None
