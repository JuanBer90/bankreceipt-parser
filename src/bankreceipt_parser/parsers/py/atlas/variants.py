"""Canonical Atlas receipt-variant identifiers shared by detection and parsing."""

from __future__ import annotations

from enum import StrEnum


class AtlasVariant(StrEnum):
    """Distinct Atlas transfer receipt interface structures."""

    TRANSFER_RECEIPT = "transfer_receipt"
