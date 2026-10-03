"""Sudameris receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class SudamerisVariant(StrEnum):
    """Structural Sudameris receipt formats."""

    TRANSFER_RECEIPT = "transfer_receipt"
