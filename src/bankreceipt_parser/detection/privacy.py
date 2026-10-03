"""Redact potentially sensitive substrings from developer-facing reports."""

from __future__ import annotations

import re

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d[\d.\s]{5,}\d\b"), "[amount-redacted]"),
    (re.compile(r"\b\d{6,}\b"), "[number-redacted]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[email-redacted]"),
    (re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"), "[date-redacted]"),
)


def redact_sensitive_text(value: str) -> str:
    """Best-effort redaction for local research output (not a security guarantee)."""
    redacted = value
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
