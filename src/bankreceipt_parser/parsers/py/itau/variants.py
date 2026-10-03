"""Itaú Paraguay receipt layout variants (aligned with detection profiles)."""

from __future__ import annotations

from enum import StrEnum


class ItauVariant(StrEnum):
    """Variant ids must match ``detection/profiles/py/itau.py``."""

    TRANSACTION_REGISTERED = "transaction_registered"
    TRANSFER_RECEIPT = "transfer_receipt"
