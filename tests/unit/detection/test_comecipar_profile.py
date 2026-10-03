"""COMECIPAR detection profile tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.profiles.py.comecipar import COMECIPAR_TRANSFER_SUCCESS
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.8, height=0.03),
        line_index=int(y * 100),
    )


def _ocr(pairs: list[tuple[str, float]]) -> OCRResult:
    lines = [text for text, _y in pairs]
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=[_el(text, y) for text, y in pairs],
    )


def test_comecipar_transfer_success_profile_accepts_structured_layout() -> None:
    result = COMECIPAR_TRANSFER_SUCCESS.evaluate(
        _ocr(
            [
                ("Transferencia", 0.05),
                ("Transferencia exitosa", 0.20),
                ("COOP COOMECIPAR LTDA", 0.45),
                ("Transferencia", 0.90),
            ]
        ),
        None,
    )
    assert result.accepted


def test_detect_comecipar_from_transfer_success_layout() -> None:
    outcome = detect_issuer_from_ocr(
        _ocr(
            [
                ("Transferencia", 0.05),
                ("Transferencia exitosa", 0.20),
                ("Coomecipar", 0.50),
                ("Transferencia", 0.90),
            ]
        )
    )
    assert outcome.issuer == "comecipar"
    assert outcome.variant == "transfer_success"
