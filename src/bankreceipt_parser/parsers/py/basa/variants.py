"""BASA receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class BasaVariant(StrEnum):
    """Structural variants for BASA receipts."""

    TRANSFER_SUCCESS = "transfer_success"
    PARTY_CARDS = "party_cards"
