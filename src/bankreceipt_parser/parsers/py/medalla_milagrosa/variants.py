"""Medalla Milagrosa receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class MedallaMilagrosaVariant(StrEnum):
    """Structural variants for Medalla Milagrosa receipts."""

    TRANSFER_OPERATION = "transfer_operation"
