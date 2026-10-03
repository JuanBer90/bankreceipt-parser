"""EKO receipt layout variants."""

from __future__ import annotations

from enum import StrEnum


class EkoVariant(StrEnum):
    """Structural variants for EKO wallet receipts."""

    SEND_RECEIPT = "send_receipt"
    TRANSFER_DETAIL = "transfer_detail"
