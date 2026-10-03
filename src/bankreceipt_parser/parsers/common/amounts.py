"""Monetary amount parsing helpers."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def parse_decimal_amount(raw: str) -> Decimal | None:
    """Parse Paraguayan-style grouped amounts such as ``20.000`` or ``15.000``."""
    cleaned = raw.strip().replace(" ", "")
    if not cleaned:
        return None
    # Thousands separator dot, no decimals in these receipts
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


_CURRENCY_AFTER_AMOUNT = r"(?:gs\s*\.?|cs\s*\.?)"
_CURRENCY_BEFORE_AMOUNT = r"(?:gs\s*\.?|cs\s*\.?)"
_PRIMARY_AMOUNT_LABELS = ("monto", "importe", "transferiste")


def extract_gs_amount(
    lines: list[str],
    full_text: str,
    *,
    variant: str | None = None,
) -> Decimal | None:
    """Extract a primary receipt amount from labeled or structurally adjacent text."""
    _ = full_text, variant
    for index, line in enumerate(lines):
        normalized = line.casefold()
        if not any(label in normalized for label in _PRIMARY_AMOUNT_LABELS):
            continue
        amount = _amount_in_text(line)
        if amount is not None:
            return amount
        for nearby in lines[index + 1 : index + 3]:
            amount = _amount_in_text(nearby)
            if amount is not None:
                return amount

    for index, line in enumerate(lines):
        if not re.fullmatch(r"\s*[\d. ,]+\s*", line):
            continue
        amount = parse_decimal_amount(line)
        if amount is None:
            continue
        if index + 1 < len(lines) and re.fullmatch(
            r"\s*" + _CURRENCY_AFTER_AMOUNT + r"\s*",
            lines[index + 1],
            flags=re.I,
        ):
            return amount

    for line in lines:
        amount = _amount_in_text(line)
        if amount is not None and any(label in line.casefold() for label in _PRIMARY_AMOUNT_LABELS):
            return amount
    return None


def _amount_in_text(text: str) -> Decimal | None:
    patterns = (
        rf"{_CURRENCY_BEFORE_AMOUNT}\s*([\d. ,]+)",
        rf"([\d. ,]+)\s*{_CURRENCY_AFTER_AMOUNT}",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            amount = parse_decimal_amount(match.group(1))
            if amount is not None:
                return amount
    return None
