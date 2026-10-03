"""BANCOP receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class BancopVariant(StrEnum):
    """Structural variants for BANCOP receipts."""

    TRANSFER_SCREEN = "transfer_screen"
