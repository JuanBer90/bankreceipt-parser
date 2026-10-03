"""Synthetic Mango issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.mango import MANGO_SIP_DETAIL, MANGO_TRANSFER_RECEIPT
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


def _sip_detail_lines() -> list[str]:
    return [
        "Detalle",
        "Transferencia SIP",
        "Enviaste",
        "Gs. 88.000",
        "DESTINATARIO EJEMPLO UNO",
        "BANCO EJEMPLO S.A.",
        "Cta. N° 301112233",
        "Origen REMITENTE EJEMPLO DOS",
        "TU FINANCIERA",
        "Cta. N° .....529",
        "Fecha y hora 01 oct 2026 - 14:53 Hs",
        "Transacción N° 9000111222",
        "Estado Transferencia enviada",
    ]


def _transfer_receipt_lines() -> list[str]:
    return [
        "Monto",
        "Gs. 22.000",
        "DESTINATARIO EJEMPLO TRES",
        "BANCO EJEMPLO S.A.",
        "Cta. N° 301112233",
        "Origen REMITENTE EJEMPLO CUATRO",
        "TU FINANCIERA",
        "Cta. N° .....487",
        "Fecha y hora 01 oct 2026 - 12:18 Hs",
        "Transacción N° aabbccdd00112233",
        "Estado Procesando transferencia",
        "mango",
    ]


def test_mango_sip_detail_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_sip_detail_lines())
    result = MANGO_SIP_DETAIL.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= MANGO_SIP_DETAIL.min_score


def test_mango_transfer_receipt_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    result = MANGO_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= MANGO_TRANSFER_RECEIPT.min_score


def test_detect_issuer_sip_detail_synthetic() -> None:
    ocr = _ocr(_sip_detail_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.MANGO
    assert outcome.variant == "sip_detail"


def test_detect_issuer_transfer_receipt_synthetic() -> None:
    ocr = _ocr(_transfer_receipt_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.MANGO
    assert outcome.variant == "transfer_receipt"


def test_eko_transfer_detail_does_not_detect_as_mango() -> None:
    lines = [
        "Detalle",
        "Enviaste",
        "Gs 44.000",
        "DESTINATARIO EJEMPLO",
        "Transferencia",
        "Compartir comprobante",
    ]
    ocr = _ocr(lines)
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer != Issuer.MANGO
