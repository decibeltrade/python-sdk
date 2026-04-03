"""Custom exceptions for the Decibel SDK.

These exceptions help callers distinguish between failures that are safe to retry
(submission errors) vs failures that require checking transaction status first
(confirmation errors).
"""

from __future__ import annotations


class TxnConfirmError(Exception):
    """
    Transaction was submitted but confirmation failed.

    Causes:
    - Transaction did not confirm within timeout (still pending or dropped)
    - Transaction executed but reverted (VM error)
    - Transaction failed during execution

    CRITICAL: The transaction MAY be on-chain. Check tx_hash status before retrying
    to avoid duplicate transactions.

    Attributes:
        tx_hash: The transaction hash that was submitted
        message: Description of what went wrong
    """

    def __init__(self, tx_hash: str, message: str) -> None:
        self.tx_hash = tx_hash
        super().__init__(f"Transaction {tx_hash}: {message}")


class TxnSubmitError(Exception):
    """
    Transaction submission failed before reaching the blockchain.

    Causes:
    - Network connectivity issues (timeout, connection refused)
    - RPC endpoint unavailable
    - HTTP errors (5xx, 429 rate limit)
    - Serialization errors

    SAFE TO RETRY: The transaction was never submitted to the blockchain.

    Attributes:
        original_exception: The underlying exception that caused the failure
    """

    def __init__(self, message: str, original_exception: Exception | None = None) -> None:
        self.original_exception = original_exception
        super().__init__(message)
