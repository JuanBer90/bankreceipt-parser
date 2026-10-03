"""Structured OCR API tests."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from PIL import Image

from bankreceipt_parser import extract_ocr, extract_text
from bankreceipt_parser.detection.profiles.py.bancop import BANCOP_TRANSFER_SCREEN
from bankreceipt_parser.ocr.pipeline import extract_ocr_with_oriented_image
from bankreceipt_parser.ocr.preprocessing import PreprocessOptions
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from helpers.synthetic_images import render_text_image


def test_extract_ocr_returns_elements() -> None:
    image = render_text_image(["COMPROBANTE", "Linea dos"])
    structured = OCRResult(
        text="COMPROBANTE\nLinea dos",
        image_width=800,
        image_height=600,
        elements=[
            OCRTextElement(
                text="COMPROBANTE",
                bbox=NormalizedBoundingBox(x=0.1, y=0.1, width=0.5, height=0.05),
            )
        ],
        warnings=(),
    )
    with patch(
        "bankreceipt_parser.ocr.pipeline.TesseractOCREngine.run_structured_on_image",
        return_value=structured,
    ):
        result = extract_ocr(image)
        assert result.text == structured.text
        assert len(result.elements) == 1
        assert extract_text(image) == structured.text


class _StaticEngine:
    def __init__(self) -> None:
        self.image_size: tuple[int, int] | None = None

    def extract_text(self, image: bytes) -> str:
        with Image.open(BytesIO(image)) as decoded:
            self.image_size = decoded.size
        return "synthetic"


class _StructuredEngine:
    def extract_text(self, image: bytes) -> str:
        return "fallback should not be used"

    def run_structured_on_image(self, image: Image.Image) -> OCRResult:
        return OCRResult(
            text="structured",
            image_width=image.width,
            image_height=image.height,
            elements=[
                OCRTextElement(
                    text="structured",
                    bbox=NormalizedBoundingBox(x=0.1, y=0.2, width=0.4, height=0.1),
                )
            ],
        )


def test_oriented_image_shared_by_ocr_and_visual_detection() -> None:
    # The blue strip is stored on the raw image's left edge. EXIF orientation 6
    # rotates it into the top band, where BANCOP's visual profile expects it.
    source = Image.new("RGB", (200, 100), "white")
    for x in range(80):
        for y in range(100):
            source.putpixel((x, y), (0, 112, 176))
    exif = source.getexif()
    exif[274] = 6
    encoded = BytesIO()
    source.save(encoded, format="JPEG", exif=exif)

    engine = _StaticEngine()
    _ocr, oriented = extract_ocr_with_oriented_image(
        encoded.getvalue(),
        ocr_engine=engine,
        preprocess_options=PreprocessOptions(min_side_px=1, max_side_px=10000, apply_clahe=False),
    )
    assert oriented.size == (100, 200)
    assert engine.image_size == oriented.size

    profile_ocr = OCRResult(
        text="Transferencias\nOperacion realizada\nCompartir comprobante",
        image_width=oriented.width,
        image_height=oriented.height,
        elements=[
            OCRTextElement(
                text="Transferencias",
                bbox=NormalizedBoundingBox(x=0.1, y=0.04, width=0.7, height=0.04),
            ),
            OCRTextElement(
                text="Operacion realizada",
                bbox=NormalizedBoundingBox(x=0.1, y=0.10, width=0.7, height=0.04),
            ),
            OCRTextElement(
                text="Compartir comprobante",
                bbox=NormalizedBoundingBox(x=0.1, y=0.70, width=0.7, height=0.04),
            ),
        ],
    )
    assert BANCOP_TRANSFER_SCREEN.evaluate(profile_ocr, oriented).accepted


def test_pipeline_uses_structured_engine_without_tesseract_type_check() -> None:
    result = extract_ocr(render_text_image(["synthetic"]), ocr_engine=_StructuredEngine())
    assert result.text == "structured"
    assert result.elements[0].bbox.y == 0.2
