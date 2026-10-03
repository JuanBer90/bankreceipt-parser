"""ECLUB receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class EclubVariant(StrEnum):
    """Structural variants for ECLUB receipts."""

    TRANSFER_SCREEN = "transfer_screen"
