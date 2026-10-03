"""Mango wallet receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class MangoVariant(StrEnum):
    """Structural variants observed on Mango transfer receipts."""

    SIP_DETAIL = "sip_detail"
    TRANSFER_RECEIPT = "transfer_receipt"
