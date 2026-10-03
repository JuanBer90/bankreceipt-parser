"""Synthetic Continental issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.continental import CONTINENTAL_TRANSFER_RECEIPT
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.8, height=0.03),
        line_index=int(y * 100),
    )


def _ocr(lines: list[str]) -> OCRResult:
    # Title signals use UPPER region (y >= 0.12); place header lines there.
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=[_el(line, 0.14 + index * 0.03) for index, line in enumerate(lines)],
    )


def _transfer_receipt_lines() -> list[str]:
    return [
        "continental",
        "Comprobante de transferencia",
        "15/03/2026 - 10:15:30",
        "Detalles",
        "Comprobante 900011122",
        "Concepto SERVICIO",
        "Monto debitado 120.000 GS.",
        "Destino",
        "Nombre RECIPIENTE EJEMPLO UNO",
        "Cuenta 123456789",
        "Entidad BANCO DESTINO SA",
        "Moneda PYG",
        "Origen",
        "Nombre REMITENTE, EJEMPLO DOS",
        "Cuenta **** 4321",
        "Envio realizado por Sip",
    ]


def test_continental_transfer_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    result = CONTINENTAL_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= CONTINENTAL_TRANSFER_RECEIPT.min_score


def test_detect_issuer_from_ocr_synthetic() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.CONTINENTAL
    assert outcome.variant == "transfer_receipt"
