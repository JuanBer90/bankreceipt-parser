"""FINANCIERA PYJ receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class FinancieraPyjVariant(StrEnum):
    """Structural receipt kinds observed for FINANCIERA PYJ."""

    TRANSFER_RECEIPT = "transfer_receipt"
