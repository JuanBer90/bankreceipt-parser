"""Synthetic Sudameris issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.sudameris import SUDAMERIS_TRANSFER_RECEIPT
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
        elements=[_el(line, 0.14 + index * 0.03) for index, line in enumerate(lines)],
    )


def _transfer_receipt_lines() -> list[str]:
    return [
        "SUDAMERIS",
        "Transferencia Bancaria",
        "Gs. 50.000",
        "Enviado por",
        "APELLIDO EJEMPLO, NOMBRE EJEMPLO",
        "....123456 Caja de Ahorros",
        "Enviado a",
        "DESTINATARIO EJEMPLO",
        "301112233 BANCO EJEMPLO S.A.",
        "Fecha",
        "01/10/2026 - 12:00:00",
        "Número de Soporte",
        "9000111222",
    ]


def test_sudameris_transfer_receipt_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    result = SUDAMERIS_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= SUDAMERIS_TRANSFER_RECEIPT.min_score


def test_detect_issuer_transfer_receipt_synthetic() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.SUDAMERIS
    assert outcome.variant == "transfer_receipt"
