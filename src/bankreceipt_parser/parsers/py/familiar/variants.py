"""Banco Familiar receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class FamiliarVariant(StrEnum):
    """Structural variants for Banco Familiar receipts."""

    TRANSFER_LOADED = "transfer_loaded"
    TRANSFER_CONFIRMED = "transfer_confirmed"
