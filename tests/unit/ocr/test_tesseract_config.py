"""Tests for Tesseract language resolution."""

from __future__ import annotations

from bankreceipt_parser.ocr.tesseract_config import resolve_tesseract_language


def test_resolve_language_prefers_spanish() -> None:
    choice = resolve_tesseract_language({"eng", "spa", "osd"})
    assert choice.lang == "spa+eng"
    assert choice.warnings == ()


def test_resolve_language_spanish_only() -> None:
    choice = resolve_tesseract_language({"spa", "osd"})
    assert choice.lang == "spa"
    assert choice.warnings == ()


def test_resolve_language_falls_back_to_english() -> None:
    choice = resolve_tesseract_language({"eng", "osd"})
    assert choice.lang == "eng"
    assert len(choice.warnings) == 1
    assert "spa" in choice.warnings[0].lower()


def test_resolve_language_default_when_no_pack() -> None:
    choice = resolve_tesseract_language({"osd"})
    assert choice.lang == ""
    assert choice.warnings
