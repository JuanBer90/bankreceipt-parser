"""COMECIPAR receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class ComeciparVariant(StrEnum):
    """Structural variants for COMECIPAR receipts."""

    TRANSFER_SUCCESS = "transfer_success"
