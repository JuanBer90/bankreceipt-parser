"""BANCOP detection profile tests."""

from __future__ import annotations

from PIL import Image

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.profiles.py.bancop import BANCOP_TRANSFER_SCREEN
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _ocr(lines: list[tuple[str, float]]) -> OCRResult:
    return OCRResult(
        text="\n".join(text for text, _ in lines),
        image_width=400,
        image_height=800,
        elements=[
            OCRTextElement(
                text=text,
                bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.6, height=0.04),
                line_index=index,
            )
            for index, (text, y) in enumerate(lines)
        ],
    )


def test_bancop_transfer_screen_profile_accepts_blue_shell() -> None:
    image = Image.new("RGB", (400, 800), (0, 112, 176))
    result = BANCOP_TRANSFER_SCREEN.evaluate(
        _ocr(
            [
                ("Transferencias", 0.04),
                ("Operacion realizada", 0.10),
                ("Compartir comprobante", 0.7),
            ]
        ),
        image,
    )
    assert result.accepted


def test_detect_bancop_transfer_screen() -> None:
    image = Image.new("RGB", (400, 800), (0, 112, 176))
    outcome = detect_issuer_from_ocr(
        _ocr(
            [
                ("Transferencias", 0.04),
                ("Operacion realizada", 0.10),
                ("Origen", 0.3),
                ("Destino", 0.5),
                ("Compartir comprobante", 0.7),
            ]
        ),
        image=image,
    )
    assert outcome.issuer == "bancop"
    assert outcome.variant == "transfer_screen"
