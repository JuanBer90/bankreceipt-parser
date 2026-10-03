"""Datetime parsing for Paraguay receipt formats."""

from __future__ import annotations

import re
from datetime import datetime


def parse_occurred_at(text: str) -> datetime | None:
    """
    Parse common printed datetime formats on Paraguayan receipts.

    Returns a naive datetime representing the local wall-clock time printed on the
    receipt. Paraguayan receipts do not encode a timezone, so this must not be
    converted to UTC or assigned a fixed offset.
    """
    parsers = (
        _parse_realizada_el_spanish,
        _parse_dd_mm_yyyy_space_hh_mm_hs,
        _parse_dd_mm_yyyy_dash_hh_mm,
        _parse_dd_mm_yyyy_space_hh_mm_ss,
        _parse_dd_mm_yyyy_a_las_hms,
        _parse_dd_mm_yyyy_las_h,
        _parse_iso_datetime,
    )
    for parser in parsers:
        result = parser(text)
        if result is not None:
            return result
    return None


_SPANISH_MONTH_ABBR: dict[str, int] = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def _parse_realizada_el_spanish(text: str) -> datetime | None:
    match = re.search(
        r"realizada\s+el\s+(\d{1,2})\s+([a-z]{3})\.?\s+(\d{4})\s+a\s+las\s+(\d{1,2}):(\d{2})\s*hs",
        text,
        flags=re.I,
    )
    if not match:
        return None
    day_s, month_s, year_s, hour_s, minute_s = match.groups()
    month = _SPANISH_MONTH_ABBR.get(month_s.casefold())
    if month is None:
        return None
    return _safe_datetime(int(year_s), month, int(day_s), int(hour_s), int(minute_s))


def _parse_dd_mm_yyyy_space_hh_mm_hs(text: str) -> datetime | None:
    match = re.search(
        r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})\s*hs",
        text,
        flags=re.I,
    )
    if not match:
        return None
    day, month, year, hour, minute = match.groups()
    return _safe_datetime(int(year), int(month), int(day), int(hour), int(minute))


def _parse_dd_mm_yyyy_space_hh_mm_ss(text: str) -> datetime | None:
    match = re.search(
        r"(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?",
        text,
    )
    if not match:
        return None
    day, month, year, hour, minute, second = match.groups()
    ss = int(second) if second else 0
    return _safe_datetime(int(year), int(month), int(day), int(hour), int(minute), ss)


def _parse_dd_mm_yyyy_a_las_hms(text: str) -> datetime | None:
    match = re.search(
        r"(\d{2})/(\d{2})/(\d{4})\s+a\s+las\s+(\d{1,2}):(\d{2})(?::(\d{2}))?",
        text,
        flags=re.I,
    )
    if not match:
        return None
    day, month, year, hour, minute, second = match.groups()
    ss = int(second) if second else 0
    return _safe_datetime(int(year), int(month), int(day), int(hour), int(minute), ss)


def _parse_dd_mm_yyyy_las_h(text: str) -> datetime | None:
    match = re.search(
        r"(\d{2})/(\d{2})/(\d{4})(?:\s+(?:a\s+)?las\s+(\d{2}):(\d{2})\s*h)?",
        text,
        flags=re.I,
    )
    if not match:
        return None
    day, month, year, hour, minute = match.groups()
    hh = int(hour) if hour else 0
    mm = int(minute) if minute else 0
    return _safe_datetime(int(year), int(month), int(day), hh, mm)


def _parse_dd_mm_yyyy_dash_hh_mm(text: str) -> datetime | None:
    match = re.search(
        r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2}):(\d{2})(?::(\d{2}))?",
        text,
        flags=re.I,
    )
    if not match:
        return None
    day, month, year, hour, minute, second = match.groups()
    ss = int(second) if second else 0
    return _safe_datetime(int(year), int(month), int(day), int(hour), int(minute), ss)


def _parse_iso_datetime(text: str) -> datetime | None:
    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?",
        text,
        flags=re.I,
    )
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    ss = int(second) if second else 0
    return _safe_datetime(int(year), int(month), int(day), int(hour), int(minute), ss)


def _safe_datetime(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int = 0,
) -> datetime | None:
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
