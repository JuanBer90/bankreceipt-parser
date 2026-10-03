"""Tests for TesseractOCREngine (mocked; no local binary required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytesseract
import pytest
from PIL import Image

from bankreceipt_parser.exceptions import OCRProcessingError, OCRUnavailableError
from bankreceipt_parser.ocr.images import encode_png
from bankreceipt_parser.ocr.tesseract import TesseractOCREngine

_IMAGE_TO_STRING = "bankreceipt_parser.ocr.tesseract.pytesseract.image_to_string"
_IMAGE_TO_DATA = "bankreceipt_parser.ocr.tesseract.pytesseract.image_to_data"


def _structured_data(text: str = "Hola") -> dict[str, list[object]]:
    return {
        "level": [4],
        "text": [text],
        "conf": [90],
        "left": [0],
        "top": [0],
        "width": [10],
        "height": [10],
        "line_num": [1],
        "block_num": [1],
    }


def test_tesseract_engine_calls_pytesseract_with_spanish() -> None:
    image = Image.new("L", (200, 100), color=255)
    engine = TesseractOCREngine()
    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["spa", "eng"]),
        patch(_IMAGE_TO_DATA, return_value={"text": []}),
        patch(_IMAGE_TO_STRING, return_value="Hola\n") as ocr,
    ):
        result = engine.run_on_image(image)
    assert "Hola" in result.text
    ocr.assert_called_once()
    _args, kwargs = ocr.call_args
    assert kwargs["lang"] == "spa+eng"


def test_tesseract_engine_language_fallback_warning() -> None:
    image = Image.new("L", (200, 100), color=255)
    engine = TesseractOCREngine()
    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["eng"]),
        patch(_IMAGE_TO_DATA, return_value={"text": []}),
        patch(_IMAGE_TO_STRING, return_value="Hello\n"),
    ):
        result = engine.run_on_image(image)
    assert result.warnings
    assert "spa" in result.warnings[0].lower()


def test_tesseract_missing_executable() -> None:
    engine = TesseractOCREngine()
    with (
        patch(
            "bankreceipt_parser.ocr.tesseract.pytesseract.get_tesseract_version",
            side_effect=pytesseract.TesseractNotFoundError,
        ),
        pytest.raises(OCRUnavailableError, match="not installed"),
    ):
        engine.run_on_image(Image.new("L", (10, 10)))


def test_tesseract_ocr_failure_wrapped() -> None:
    engine = TesseractOCREngine()
    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["eng"]),
        patch(_IMAGE_TO_DATA, return_value={"text": []}),
        patch(
            _IMAGE_TO_STRING,
            side_effect=OSError("boom"),
        ),
        pytest.raises(OCRProcessingError, match="failed"),
    ):
        engine.run_on_image(Image.new("L", (10, 10)))


def test_tesseract_empty_output_raises() -> None:
    engine = TesseractOCREngine()
    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["eng"]),
        patch(_IMAGE_TO_DATA, return_value={"text": []}),
        patch(_IMAGE_TO_STRING, return_value="   \n"),
        pytest.raises(OCRProcessingError, match="empty"),
    ):
        engine.run_on_image(Image.new("L", (10, 10)))


def test_extract_text_protocol_uses_bytes() -> None:
    engine = TesseractOCREngine()
    png = encode_png(Image.new("L", (50, 50), color=255))
    mock_result = MagicMock(text="ok", warnings=())
    with patch.object(engine, "run_on_image", return_value=mock_result) as run:
        assert engine.extract_text(png) == "ok"
    run.assert_called_once()


def test_tesseract_command_is_scoped_per_engine_instance() -> None:
    original = pytesseract.pytesseract.tesseract_cmd
    first = TesseractOCREngine(tesseract_cmd="/opt/tesseract-first")
    second = TesseractOCREngine(tesseract_cmd="/opt/tesseract-second")

    def command_seen_by_tesseract(*_args: object, **_kwargs: object) -> str:
        return pytesseract.pytesseract.tesseract_cmd

    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["eng"]),
        patch(_IMAGE_TO_DATA, return_value={"text": []}),
        patch(_IMAGE_TO_STRING, side_effect=command_seen_by_tesseract),
    ):
        assert first.run_on_image(Image.new("L", (10, 10))).text == "/opt/tesseract-first"
        assert second.run_on_image(Image.new("L", (10, 10))).text == "/opt/tesseract-second"

    assert pytesseract.pytesseract.tesseract_cmd == original


def test_tesseract_uses_structured_text_without_redundant_string_call() -> None:
    engine = TesseractOCREngine()
    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["eng"]),
        patch(_IMAGE_TO_DATA, return_value=_structured_data()),
        patch(_IMAGE_TO_STRING) as image_to_string,
    ):
        result = engine.run_on_image(Image.new("L", (20, 20)))

    assert result.text == "Hola"
    image_to_string.assert_not_called()


def test_tesseract_caches_availability_and_languages_per_engine() -> None:
    engine = TesseractOCREngine()
    with (
        patch(
            "bankreceipt_parser.ocr.tesseract.pytesseract.get_tesseract_version",
        ) as version,
        patch(
            "bankreceipt_parser.ocr.tesseract.pytesseract.get_languages",
            return_value=["eng"],
        ) as languages,
        patch(_IMAGE_TO_DATA, return_value=_structured_data()),
        patch(_IMAGE_TO_STRING) as image_to_string,
    ):
        engine.run_on_image(Image.new("L", (20, 20)))
        engine.run_on_image(Image.new("L", (20, 20)))

    assert version.call_count == 1
    assert languages.call_count == 1
    assert image_to_string.call_count == 0
