"""Canonical BNF receipt-variant identifiers shared by detection and parsing."""

from __future__ import annotations

from enum import StrEnum


class BnfVariant(StrEnum):
    """Distinct BNF transfer receipt interface structures."""

    TRANSFER_SENT_CARD = "transfer_sent_card"
    OPERATION_SUCCESS_RECEIPT = "operation_success_receipt"
