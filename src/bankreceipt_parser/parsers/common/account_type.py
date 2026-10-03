"""Account product type detection from receipt OCR text."""

from __future__ import annotations

from bankreceipt_parser.models.enums import AccountType
from bankreceipt_parser.parsers.common.lines import normalize_label


def account_type_from_text(text: str) -> AccountType:
    """Map account-product wording on already-extracted receipt text to AccountType."""
    norm = normalize_label(text)
    if "ahorro" in norm or "ahorros" in norm:
        return AccountType.SAVINGS
    if "corriente" in norm:
        return AccountType.CHECKING
    if norm == "cc":
        return AccountType.CHECKING
    if norm == "ah":
        return AccountType.SAVINGS
    return AccountType.UNKNOWN
