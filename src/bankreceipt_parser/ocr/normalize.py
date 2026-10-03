"""Safe, OCR-level text normalization (not bank-field parsing)."""

from __future__ import annotations

import re


def normalize_ocr_text(text: str) -> str:
    """Normalize line endings and whitespace without altering semantic content."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    collapsed = _collapse_blank_lines(lines)
    return "\n".join(collapsed).strip()


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        result.append(line)
        previous_blank = is_blank
    while result and result[0] == "":
        result.pop(0)
    while result and result[-1] == "":
        result.pop()
    return result


def is_mostly_blank(text: str) -> bool:
    """Return True when OCR output contains no meaningful characters."""
    return not re.search(r"[^\s\u200b\u200c\u200d\ufeff]", text)
