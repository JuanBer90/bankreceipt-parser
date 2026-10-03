"""Internal OCR pipeline: load, preprocess, recognize, normalize."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from bankreceipt_parser.ocr.engine import OCREngine, StructuredOCREngine
from bankreceipt_parser.ocr.images import (
    ImageSource,
    encode_png,
    load_image,
    normalize_image_orientation,
)
from bankreceipt_parser.ocr.normalize import normalize_ocr_text
from bankreceipt_parser.ocr.preprocessing import PreprocessOptions, preprocess_image
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.ocr.tesseract import TesseractOCREngine


@dataclass(frozen=True)
class ExtractTextResult:
    """OCR text and non-fatal warnings (e.g. language pack fallback)."""

    text: str
    warnings: tuple[str, ...]


def extract_text_with_details(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
) -> ExtractTextResult:
    """Run the full local OCR pipeline on an image path or bytes."""
    structured = extract_ocr_with_details(
        source,
        ocr_engine=ocr_engine,
        preprocess_options=preprocess_options,
    )
    return ExtractTextResult(text=structured.text, warnings=structured.warnings)


def extract_ocr_with_details(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
) -> OCRResult:
    """Run OCR and return structured text + spatial elements."""
    structured, _oriented = extract_ocr_with_oriented_image(
        source,
        ocr_engine=ocr_engine,
        preprocess_options=preprocess_options,
    )
    return structured


def extract_ocr_with_oriented_image(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
) -> tuple[OCRResult, Image.Image]:
    """Run OCR and retain the oriented image used for visual detection."""
    image, _fmt = load_image(source)
    oriented = normalize_image_orientation(image)
    processed = preprocess_image(oriented, preprocess_options, assume_oriented=True)

    if ocr_engine is None:
        engine = TesseractOCREngine()
        return engine.run_structured_on_image(processed), oriented

    if isinstance(ocr_engine, StructuredOCREngine):
        return ocr_engine.run_structured_on_image(processed), oriented

    raw = ocr_engine.extract_text(encode_png(processed))
    text = normalize_ocr_text(raw)
    width, height = processed.size
    return (
        OCRResult(text=text, elements=[], image_width=width, image_height=height, warnings=()),
        oriented,
    )
