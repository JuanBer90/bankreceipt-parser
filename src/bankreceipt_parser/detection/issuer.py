"""Issuer detection from OCR text and optional QR payload."""

from __future__ import annotations

from PIL import Image

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus, IssuerDetectionOutcome
from bankreceipt_parser.ocr.images import ImageSource
from bankreceipt_parser.ocr.structure import OCRResult


def detect_issuer(
    *,
    text: str | None = None,
    qr_data: str | None = None,
    ocr: OCRResult | None = None,
    image: ImageSource | Image.Image | None = None,
) -> IssuerDetectionOutcome:
    """
    Detect receipt issuer/format.

    When structured OCR is available, spatial/text signals are used. Plain text-only
    input remains supported but cannot use layout information.
    """
    if ocr is None and text is None:
        return IssuerDetectionOutcome(
            status=DetectionStatus.UNKNOWN,
            notes=("No OCR text provided.",),
        )
    if ocr is not None:
        structured = ocr
    else:
        structured = OCRResult(text=text or "", elements=[], image_width=1, image_height=1)
    outcome = detect_issuer_from_ocr(structured, image=image)
    _ = qr_data
    return outcome


def detect_issuer_key(
    *,
    text: str,
    qr_data: str | None = None,
    ocr: OCRResult | None = None,
    image: ImageSource | Image.Image | None = None,
) -> str | None:
    """Backward-compatible helper returning an issuer key when identified."""
    outcome = detect_issuer(text=text, qr_data=qr_data, ocr=ocr, image=image)
    if outcome.status == DetectionStatus.UNKNOWN:
        return None
    return outcome.issuer
