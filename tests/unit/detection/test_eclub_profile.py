"""ECLUB detection profile tests."""

from __future__ import annotations

from PIL import Image

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.profiles.py.eclub import ECLUB_TRANSFER_SCREEN
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.6, height=0.04),
        line_index=int(y * 100),
    )


def _ocr(lines: list[tuple[str, float]]) -> OCRResult:
    return OCRResult(
        text="\n".join(text for text, _ in lines),
        image_width=400,
        image_height=800,
        elements=[_el(text, y) for text, y in lines],
    )


def test_eclub_transfer_screen_profile_accepts_magenta_shell() -> None:
    image = Image.new("RGB", (400, 800), (200, 0, 64))
    result = ECLUB_TRANSFER_SCREEN.evaluate(
        _ocr(
            [
                ("Transferencia realizada", 0.18),
                ("Estado", 0.40),
            ]
        ),
        image,
    )
    assert result.accepted


def test_detect_eclub_transfer_screen() -> None:
    image = Image.new("RGB", (400, 800), (200, 0, 64))
    outcome = detect_issuer_from_ocr(
        _ocr(
            [
                ("Transferencia realizada", 0.18),
                ("Estado", 0.40),
                ("Beneficiario", 0.50),
            ]
        ),
        image=image,
    )
    assert outcome.issuer == "eclub"
    assert outcome.variant == "transfer_screen"
