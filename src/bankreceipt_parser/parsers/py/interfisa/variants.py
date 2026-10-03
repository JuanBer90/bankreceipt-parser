"""INTERFISA receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class InterfisaVariant(StrEnum):
    """Structural INTERFISA receipt formats."""

    TRANSFER_LOADED = "transfer_loaded"
