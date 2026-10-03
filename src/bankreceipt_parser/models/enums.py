"""Shared enumerations for receipt models."""

from __future__ import annotations

from enum import StrEnum


class TransferStatus(StrEnum):
    """Normalized transfer outcome."""

    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AccountType(StrEnum):
    """Normalized account product type."""

    CHECKING = "checking"
    SAVINGS = "savings"
    WALLET = "wallet"
    OTHER = "other"
    UNKNOWN = "unknown"
