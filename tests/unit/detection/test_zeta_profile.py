"""Synthetic ZETA issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.zeta import ZETA_TRANSFER_RECEIPT
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.8, height=0.03),
        line_index=int(y * 100),
    )


def _ocr(lines: list[str]) -> OCRResult:
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=[_el(line, 0.05 + index * 0.04) for index, line in enumerate(lines)],
    )


def _transfer_receipt_lines() -> list[str]:
    return [
        "zeta banco",
        "COMPROBANTE",
        "TRANSFERENCIA ENVIADA",
        "NRO. COMPROBANTE: 880011223344",
        "GS. 88.000",
        "CONCEPTO",
        "NOTA EJEMPLO",
        "PARA",
        "RECIPIENTE EJEMPLO",
        "DESDE",
        "REMITENTE EJEMPLO",
        "Compartir comprobante",
    ]


def test_zeta_transfer_receipt_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    result = ZETA_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= ZETA_TRANSFER_RECEIPT.min_score


def test_detect_issuer_transfer_receipt_synthetic() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.ZETA
    assert outcome.variant == "transfer_receipt"
