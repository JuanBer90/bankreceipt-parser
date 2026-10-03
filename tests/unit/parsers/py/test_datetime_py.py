"""Datetime parsing tests with synthetic OCR text."""

from __future__ import annotations

from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at


def test_parse_occurred_at_returns_naive_printed_local_time() -> None:
    result = parse_occurred_at("15/01/2026 las 10:30 h")
    assert result is not None
    assert result.isoformat() == "2026-01-15T10:30:00"
    assert result.tzinfo is None


def test_parse_occurred_at_returns_none_for_invalid_ocr_dates() -> None:
    for value in ("31/02/2026", "99/99/2026", "15/01/2026 las 29:75 h"):
        assert parse_occurred_at(value) is None


def test_parse_occurred_at_dd_mm_yyyy_dash_time() -> None:
    result = parse_occurred_at("30/09/2026 - 20:47")
    assert result is not None
    assert result.isoformat() == "2026-09-30T20:47:00"


def test_parse_occurred_at_dd_mm_yyyy_dash_time_with_seconds() -> None:
    result = parse_occurred_at("01/10/2026 - 15:22:07")
    assert result is not None
    assert result.isoformat() == "2026-10-01T15:22:07"


def test_parse_occurred_at_dd_mm_yyyy_a_las_with_seconds() -> None:
    result = parse_occurred_at("30/09/2026 a las 19:44:24")
    assert result is not None
    assert result.isoformat() == "2026-09-30T19:44:24"


def test_parse_occurred_at_iso_with_seconds() -> None:
    result = parse_occurred_at("Fecha de Operación 2026-10-01 15:37:33")
    assert result is not None
    assert result.isoformat() == "2026-10-01T15:37:33"


def test_parse_occurred_at_invalid_dash_date() -> None:
    assert parse_occurred_at("31/02/2026 - 20:47") is None


def test_parse_occurred_at_recepcion_midnight() -> None:
    result = parse_occurred_at("30/09/2026 00:00 hs.")
    assert result is not None
    assert result.isoformat() == "2026-09-30T00:00:00"


def test_parse_occurred_at_realizada_el_spanish_month() -> None:
    result = parse_occurred_at("realizada el 01 oct 2026 a las 09:53 hs")
    assert result is not None
    assert result.isoformat() == "2026-10-01T09:53:00"


def test_parse_occurred_at_space_separated_date_and_time() -> None:
    result = parse_occurred_at("Fecha y Hora 30/09/2026 20:13")
    assert result is not None
    assert result.isoformat() == "2026-09-30T20:13:00"


def test_parse_occurred_at_space_separated_date_and_time_with_seconds() -> None:
    result = parse_occurred_at("30/09/2026 20:31:59")
    assert result is not None
    assert result.isoformat() == "2026-09-30T20:31:59"


def test_parse_occurred_at_date_only_still_midnight() -> None:
    result = parse_occurred_at("30/09/2026")
    assert result is not None
    assert result.isoformat() == "2026-09-30T00:00:00"
