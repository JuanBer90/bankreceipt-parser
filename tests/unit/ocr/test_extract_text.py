"""Tests for the public extract_text API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bankreceipt_parser import extract_text
from bankreceipt_parser.exceptions import ImageLoadError
from bankreceipt_parser.ocr.engine import OCREngine
from bankreceipt_parser.ocr.pipeline import extract_text_with_details
from helpers.synthetic_images import render_text_image


class _StubEngine:
    def extract_text(self, image: bytes) -> str:
        assert image.startswith(b"\x89PNG")
        return "  línea uno  \r\n\r\nlínea dos  "


def test_extract_text_delegates_to_pipeline(tmp_path: Path) -> None:
    png_path = tmp_path / "receipt.png"
    png_path.write_bytes(render_text_image(["COMPROBANTE"]))
    text = extract_text(png_path, ocr_engine=_StubEngine())
    assert text == "línea uno\n\nlínea dos"


def test_extract_text_with_details_returns_warnings() -> None:
    data = render_text_image(["test"])
    engine = MagicMock(spec=OCREngine)
    engine.extract_text.return_value = "raw"
    result = extract_text_with_details(data, ocr_engine=engine)
    assert result.text == "raw"
    assert result.warnings == ()


def test_extract_text_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ImageLoadError):
        extract_text(tmp_path / "nope.png")
