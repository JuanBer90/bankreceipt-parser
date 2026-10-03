"""Tests for OCR text normalization."""

from __future__ import annotations

from bankreceipt_parser.ocr.normalize import normalize_ocr_text


def test_normalize_line_endings() -> None:
    text = "línea uno\r\nlínea dos\rlinea tres\n"
    assert normalize_ocr_text(text) == "línea uno\nlínea dos\nlinea tres"


def test_normalize_trailing_whitespace() -> None:
    assert normalize_ocr_text("monto: 1000   \nfecha: hoy  ") == "monto: 1000\nfecha: hoy"


def test_normalize_collapses_redundant_blank_lines() -> None:
    text = "a\n\n\n\nb"
    assert normalize_ocr_text(text) == "a\n\nb"


def test_normalize_preserves_meaningful_line_boundaries() -> None:
    text = "COMPROBANTE\nMonto: Gs. 50.000\nOperacion: TEST-12345"
    assert normalize_ocr_text(text) == text


def test_normalize_unicode_spanish_characters() -> None:
    text = "  Ñandú — señor ítems  "
    assert normalize_ocr_text(text) == "Ñandú — señor ítems"
