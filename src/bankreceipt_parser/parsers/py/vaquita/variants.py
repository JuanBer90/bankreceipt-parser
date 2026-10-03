"""Vaquita transfer comprobante layout variants."""

from __future__ import annotations

from enum import StrEnum


class VaquitaVariant(StrEnum):
    """Structural variants observed on Vaquita transfer comprobantes."""

    YELLOW_TRANSFER = "yellow_transfer"
