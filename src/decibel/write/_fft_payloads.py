"""Payload builders for the on-chain ``funded_first_trade`` entry functions.

``lock`` / ``lock_from_subaccount`` require the owner as signer — they move the owner's own
funds, so a session-key delegate cannot substitute. ``open_trial`` and ``unlock`` accept a
``TradePerpsAllMarkets`` delegate on the owner's primary subaccount (session-key eligible), and
``settle_trial`` is permissionless.

Because of that, :func:`build_lock_payload` and :func:`build_lock_from_subaccount_payload` have
no counterpart method on :class:`~decibel.write.DecibelWriteDex` — the SDK's signer may be a
session key, which the chain would reject. Sign them with the owner's own wallet instead::

    payload = build_lock_payload(
        campaign_package=..., campaign_addr=..., amount=..., duration_days=...
    )
    txn = await write.build_tx(payload, owner_account.address())
    await write.submit_tx(txn, write._sign_transaction(owner_account, txn))

The other three builders are wrapped by ``open_fft_trial`` / ``claim_fft_unlock`` /
``settle_fft_trial``.

Argument convention, mirroring the TypeScript SDK: ``u64`` values go on the wire as decimal
strings (they can exceed the JSON-safe integer range once a payload leaves Python for a wallet
adapter), narrower ints go as plain ints.
"""

from __future__ import annotations

from decibel._transaction_builder import InputEntryFunctionData

__all__ = [
    "build_lock_payload",
    "build_lock_from_subaccount_payload",
    "build_claim_unlock_payload",
    "build_settle_trial_payload",
    "build_open_trial_payload",
]


def build_lock_payload(
    *,
    campaign_package: str,
    campaign_addr: str,
    amount: int,
    duration_days: int,
) -> InputEntryFunctionData:
    """Lock ``amount`` (raw chain units, USDC x 10^6) from the wallet store.

    ``duration_days`` must sit within the ``campaign_lock`` duration bounds (default 1-49).
    """
    return InputEntryFunctionData(
        function=f"{campaign_package}::funded_first_trade::lock",
        type_arguments=[],
        function_arguments=[campaign_addr, str(amount), duration_days],
    )


def build_lock_from_subaccount_payload(
    *,
    campaign_package: str,
    campaign_addr: str,
    amount: int,
    duration_days: int,
) -> InputEntryFunctionData:
    """Fund the lock from the owner's primary subaccount instead of the wallet store."""
    return InputEntryFunctionData(
        function=f"{campaign_package}::funded_first_trade::lock_from_subaccount",
        type_arguments=[],
        function_arguments=[campaign_addr, str(amount), duration_days],
    )


def build_claim_unlock_payload(
    *,
    campaign_package: str,
    campaign_addr: str,
    lock_id: int,
    owner: str,
) -> InputEntryFunctionData:
    """Claim a matured lock (the on-chain entry is named ``unlock``)."""
    return InputEntryFunctionData(
        function=f"{campaign_package}::funded_first_trade::unlock",
        type_arguments=[],
        function_arguments=[campaign_addr, str(lock_id), owner],
    )


def build_settle_trial_payload(
    *,
    campaign_package: str,
    campaign_addr: str,
    trial_id: int,
) -> InputEntryFunctionData:
    """Permissionless keeper entry — any signer can settle an expired trial.

    Exposed to users as the backup path when the keeper is down.
    """
    return InputEntryFunctionData(
        function=f"{campaign_package}::funded_first_trade::settle_trial",
        type_arguments=[],
        function_arguments=[campaign_addr, str(trial_id)],
    )


def build_open_trial_payload(
    *,
    campaign_package: str,
    campaign_addr: str,
    owner: str,
) -> InputEntryFunctionData:
    """Open a trial for ``owner``.

    There is no side argument by design: the trial's side is drawn on-chain via randomness.
    """
    return InputEntryFunctionData(
        function=f"{campaign_package}::funded_first_trade::open_trial",
        type_arguments=[],
        function_arguments=[campaign_addr, owner],
    )
