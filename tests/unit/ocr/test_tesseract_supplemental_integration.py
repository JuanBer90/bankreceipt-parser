"""Tesseract engine wiring for primary PSM 6 + supplemental PSM 3 merge (mocked)."""

from __future__ import annotations

from unittest.mock import patch

from PIL import Image

from bankreceipt_parser.ocr.tesseract import TesseractOCREngine
from bankreceipt_parser.ocr.tesseract_config import (
    DEFAULT_TESSERACT_CONFIG,
    SUPPLEMENTAL_TESSERACT_CONFIG,
)
from bankreceipt_parser.ocr.tesseract_data import build_ocr_result_from_tesseract_data
from helpers.supplemental_ocr import (
    fictional_primary_without_centered_amount,
    fictional_supplemental_amount_in_gap,
)

_IMAGE_TO_DATA = "bankreceipt_parser.ocr.tesseract.pytesseract.image_to_data"
_IMAGE_TO_STRING = "bankreceipt_parser.ocr.tesseract.pytesseract.image_to_string"


def test_run_structured_on_image_merges_supplemental_pass() -> None:
    """Engine must run two ``image_to_data`` passes and merge gap-fill words into OCR text."""
    primary_data = fictional_primary_without_centered_amount()
    supplemental_data = fictional_supplemental_amount_in_gap()
    configs_seen: list[str] = []

    def fake_image_to_data(
        _image: Image.Image,
        *,
        lang: str | None = None,
        config: str | None = None,
        output_type: object = None,
    ) -> dict[str, list[object]]:
        _ = lang, output_type
        configs_seen.append(config or "")
        if config == DEFAULT_TESSERACT_CONFIG:
            return primary_data
        if config == SUPPLEMENTAL_TESSERACT_CONFIG:
            return supplemental_data
        return {"text": []}

    engine = TesseractOCREngine()
    with (
        patch.object(TesseractOCREngine, "_ensure_available"),
        patch.object(TesseractOCREngine, "_list_languages", return_value=["eng"]),
        patch(_IMAGE_TO_DATA, side_effect=fake_image_to_data) as image_to_data,
        patch(_IMAGE_TO_STRING) as image_to_string,
    ):
        result = engine.run_structured_on_image(Image.new("L", (1000, 1000), color=255))

    assert image_to_data.call_count == 2
    assert DEFAULT_TESSERACT_CONFIG in configs_seen
    assert SUPPLEMENTAL_TESSERACT_CONFIG in configs_seen
    image_to_string.assert_not_called()

    primary_only = build_ocr_result_from_tesseract_data(
        data=primary_data,
        image_width=1000,
        image_height=1000,
    )
    assert "88.500" not in primary_only.text

    assert "COMPROBANTE TRANSFERENCIA EJEMPLO" in result.text
    assert "88.500" in result.text
    assert "Gs." in result.text
    merged_lines = [line for line in result.text.splitlines() if line.strip()]
    assert merged_lines.index("COMPROBANTE TRANSFERENCIA EJEMPLO") < merged_lines.index(
        "Gs. 88.500"
    )
    assert merged_lines.index("Gs. 88.500") < merged_lines.index("CONCEPTO PAGO EJEMPLO")
