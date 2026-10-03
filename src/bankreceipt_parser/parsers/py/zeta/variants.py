"""ZETA Banco receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class ZetaVariant(StrEnum):
    """Structural variants for ZETA transfer comprobantes."""

    TRANSFER_RECEIPT = "transfer_receipt"
