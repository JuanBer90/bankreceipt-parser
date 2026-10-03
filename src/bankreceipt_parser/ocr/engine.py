"""OCR engine abstraction (implementations must not leak into parsers)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PIL import Image

from bankreceipt_parser.exceptions import OCRError
from bankreceipt_parser.ocr.structure import OCRResult


@runtime_checkable
class OCREngine(Protocol):
    """Extract plain text from a preprocessed encoded image (PNG bytes)."""

    def extract_text(self, image: bytes) -> str:
        """Return OCR text for the given encoded image bytes."""
        ...


@runtime_checkable
class StructuredOCREngine(OCREngine, Protocol):
    """Optional capability for OCR engines that preserve text geometry."""

    def run_structured_on_image(self, image: Image.Image) -> OCRResult:
        """Return text, elements, and dimensions for a preprocessed image."""
        ...


class NotImplementedOCREngine:
    """Placeholder when no OCR backend is configured."""

    def extract_text(self, image: bytes) -> str:
        raise OCRError("OCR engine is not configured.")
