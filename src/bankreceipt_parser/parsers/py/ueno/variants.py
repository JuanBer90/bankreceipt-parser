"""Canonical UENO receipt-variant identifiers shared by detection and parsing."""

from __future__ import annotations

from enum import StrEnum


class UenoVariant(StrEnum):
    """Distinct UENO receipt interface structures."""

    TRANSFER_RECEIPT = "transfer_receipt"
    PAYMENT_RECEIPT = "payment_receipt"
    MOVEMENT_DETAIL = "movement_detail"
    TRANSFER_SUMMARY = "transfer_summary"
