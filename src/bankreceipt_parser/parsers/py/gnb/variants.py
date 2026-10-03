"""Canonical GNB receipt-variant identifiers shared by detection and parsing."""

from __future__ import annotations

from enum import StrEnum


class GnbVariant(StrEnum):
    """Distinct GNB transfer receipt interface structures."""

    TRANSFER_SUCCESS = "transfer_success"
    SPI_MOVEMENT_DETAIL = "spi_movement_detail"
