"""Banco Continental receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class ContinentalVariant(StrEnum):
    """Supported Continental receipt layouts."""

    TRANSFER_RECEIPT = "transfer_receipt"
