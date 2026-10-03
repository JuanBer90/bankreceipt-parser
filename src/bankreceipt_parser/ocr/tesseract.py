"""Tesseract-backed OCR engine."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock

import pytesseract
from PIL import Image
from pytesseract import Output

from bankreceipt_parser.exceptions import OCRProcessingError, OCRUnavailableError
from bankreceipt_parser.ocr.normalize import is_mostly_blank, normalize_ocr_text
from bankreceipt_parser.ocr.preprocessing import decode_png_bytes
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.ocr.supplemental_merge import merge_supplemental_tesseract_pass
from bankreceipt_parser.ocr.tesseract_config import (
    DEFAULT_TESSERACT_CONFIG,
    SUPPLEMENTAL_TESSERACT_CONFIG,
    resolve_tesseract_language,
)
from bankreceipt_parser.ocr.tesseract_data import build_ocr_result_from_tesseract_data

_TESSERACT_COMMAND_LOCK = RLock()


@contextmanager
def _tesseract_command_scope(command: str | None) -> Iterator[None]:
    """Temporarily configure pytesseract's process-global command under a lock."""
    with _TESSERACT_COMMAND_LOCK:
        previous = pytesseract.pytesseract.tesseract_cmd
        if command is not None:
            pytesseract.pytesseract.tesseract_cmd = command
        try:
            yield
        finally:
            pytesseract.pytesseract.tesseract_cmd = previous


@dataclass(frozen=True)
class TesseractOCRResult:
    """OCR output plus non-fatal warnings (e.g. language fallback)."""

    text: str
    warnings: tuple[str, ...]
    structured: OCRResult | None = None


class TesseractOCREngine:
    """Run local Tesseract OCR on preprocessed image bytes."""

    def __init__(self, *, tesseract_cmd: str | None = None) -> None:
        self._tesseract_cmd = tesseract_cmd
        self._availability_checked = False
        self._languages: tuple[str, ...] | None = None

    def extract_text(self, image: bytes) -> str:
        """Satisfy the OCREngine protocol using PNG (or decodable) image bytes."""
        return self.run_on_image(decode_png_bytes(image)).text

    def run_on_image(self, image: Image.Image) -> TesseractOCRResult:
        """Run OCR on a PIL image and return normalized text."""
        structured = self.run_structured_on_image(image)
        return TesseractOCRResult(
            text=structured.text,
            warnings=structured.warnings,
            structured=structured,
        )

    def run_structured_on_image(self, image: Image.Image) -> OCRResult:
        """Run OCR and return text plus normalized spatial elements."""
        with _tesseract_command_scope(self._tesseract_cmd):
            self._ensure_available()
            language_choice = resolve_tesseract_language(set(self._list_languages()))
            config = DEFAULT_TESSERACT_CONFIG
            lang = language_choice.lang or None
            width, height = image.size
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang=lang,
                    config=config,
                    output_type=Output.DICT,
                )
            except pytesseract.TesseractNotFoundError as exc:
                raise OCRUnavailableError(
                    "Tesseract OCR is not installed or not found on PATH. "
                    "Install the Tesseract binary for your system."
                ) from exc
            except pytesseract.TesseractError as exc:
                raise OCRProcessingError(f"Tesseract OCR failed: {exc}") from exc
            except OSError as exc:
                raise OCRProcessingError(f"Tesseract OCR failed: {exc}") from exc

            structured = build_ocr_result_from_tesseract_data(
                data=data,
                image_width=width,
                image_height=height,
                warnings=language_choice.warnings,
            )
            try:
                supplemental_data = pytesseract.image_to_data(
                    image,
                    lang=lang,
                    config=SUPPLEMENTAL_TESSERACT_CONFIG,
                    output_type=Output.DICT,
                )
            except (pytesseract.TesseractError, OSError):
                supplemental_data = {"text": []}
            structured = merge_supplemental_tesseract_pass(structured, supplemental_data)
            if not is_mostly_blank(structured.text):
                return structured

            try:
                raw_text = pytesseract.image_to_string(image, lang=lang, config=config)
            except pytesseract.TesseractNotFoundError as exc:
                raise OCRUnavailableError(
                    "Tesseract OCR is not installed or not found on PATH. "
                    "Install the Tesseract binary for your system."
                ) from exc
            except pytesseract.TesseractError as exc:
                raise OCRProcessingError(f"Tesseract OCR failed: {exc}") from exc
            except OSError as exc:
                raise OCRProcessingError(f"Tesseract OCR failed: {exc}") from exc

            normalized = normalize_ocr_text(raw_text)
            if is_mostly_blank(normalized):
                raise OCRProcessingError("Tesseract OCR returned empty text.")
            return structured.model_copy(update={"text": normalized})

    def _ensure_available(self) -> None:
        if self._availability_checked:
            return
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError(
                "Tesseract OCR is not installed or not found on PATH. "
                "Install the Tesseract binary for your system."
            ) from exc
        self._availability_checked = True

    def _list_languages(self) -> list[str]:
        if self._languages is not None:
            return list(self._languages)
        try:
            languages: list[str] = list(pytesseract.get_languages(config=""))
            self._languages = tuple(languages)
            return languages
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError(
                "Tesseract OCR is not installed or not found on PATH. "
                "Install the Tesseract binary for your system."
            ) from exc
        except pytesseract.TesseractError:
            self._languages = ()
            return []


def is_tesseract_installed(*, tesseract_cmd: str | None = None) -> bool:
    """Return True when the Tesseract executable is reachable."""
    with _tesseract_command_scope(tesseract_cmd):
        try:
            pytesseract.get_tesseract_version()
            return True
        except pytesseract.TesseractNotFoundError:
            return False
