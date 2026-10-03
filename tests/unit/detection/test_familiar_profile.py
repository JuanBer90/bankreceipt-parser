"""Synthetic Banco Familiar issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.familiar import (
    FAMILIAR_TRANSFER_CONFIRMED,
    FAMILIAR_TRANSFER_LOADED,
)
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


def _transfer_loaded_lines() -> list[str]:
    return [
        "Transferencia cargada con exito",
        "Monto a enviar",
        "Gs. 50.000",
        "A la cuenta de",
        "Enviado por",
        "REMITENTE EJEMPLO",
    ]


def _transfer_confirmed_lines() -> list[str]:
    return [
        "TRANSFERENCIA A OTRAS ENTIDADES CONFIRMADA",
        "Familiar a toda hora",
        "Cliente Pagador: REMITENTE EJEMPLO",
        "Moneda y Monto: PYG 10.000",
    ]


def test_familiar_transfer_loaded_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_loaded_lines())
    result = FAMILIAR_TRANSFER_LOADED.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= FAMILIAR_TRANSFER_LOADED.min_score


def test_familiar_transfer_confirmed_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_confirmed_lines())
    result = FAMILIAR_TRANSFER_CONFIRMED.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= FAMILIAR_TRANSFER_CONFIRMED.min_score


def test_detect_issuer_transfer_loaded_synthetic() -> None:
    ocr = _ocr(_transfer_loaded_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.FAMILIAR
    assert outcome.variant == "transfer_loaded"


def test_eko_send_receipt_does_not_detect_as_familiar() -> None:
    lines = [
        "Listo",
        "Envio",
        "Gs 55.000",
        "REMITENTE EJEMPLO",
        "Banco Familiar",
        "Compartir comprobante",
    ]
    outcome = detect_issuer_from_ocr(_ocr(lines))
    assert outcome.issuer != Issuer.FAMILIAR
