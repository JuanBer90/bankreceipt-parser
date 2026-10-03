"""Payment network detection from receipt OCR text."""

from __future__ import annotations

import re

from bankreceipt_parser.parsers.common.lines import normalize_label


def payment_network_from_text(full_text: str) -> str | None:
    """Return a normalized network code when SIP or SPI appears in the text."""
    norm = normalize_label(full_text)
    if re.search(r"\bsip\b", norm):
        return "SIP"
    if "sistema de pagos" in norm:
        return "SIP"
    if re.search(r"\bspi\b", norm):
        return "SPI"
    return None
