"""OCR subsystem."""

from bankreceipt_parser.ocr.engine import NotImplementedOCREngine, OCREngine
from bankreceipt_parser.ocr.images import ImageSource, load_image
from bankreceipt_parser.ocr.normalize import normalize_ocr_text
from bankreceipt_parser.ocr.preprocessing import (
    PreprocessOptions,
    preprocess_for_ocr,
    preprocess_image,
)
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.ocr.tesseract import TesseractOCREngine, is_tesseract_installed

__all__ = [
    "ImageSource",
    "NotImplementedOCREngine",
    "OCREngine",
    "PreprocessOptions",
    "NormalizedBoundingBox",
    "OCRResult",
    "OCRTextElement",
    "TesseractOCREngine",
    "is_tesseract_installed",
    "load_image",
    "normalize_ocr_text",
    "preprocess_for_ocr",
    "preprocess_image",
]
