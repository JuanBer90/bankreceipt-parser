"""Synthetic INTERFISA issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.interfisa import INTERFISA_TRANSFER_LOADED
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
        "TRANSFERENCIA CARGADA",
        "Nro de Transaccion:",
        "900012345",
        "15/01/2026 10:20:30",
        "APELLIDO EJEMPLO, NOMBRE EJEMPLO",
        "Cuenta debito",
        "800011122",
        "GS 88.500",
        "Motivo:",
        "Pago servicios ejemplo",
        "900099988",
        "Banco Beneficiario",
        "BANCO DESTINO S.A.E.",
        "Documento Beneficiario",
        "CI - 1234567",
    ]


def test_interfisa_transfer_loaded_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_transfer_loaded_lines())
    result = INTERFISA_TRANSFER_LOADED.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= INTERFISA_TRANSFER_LOADED.min_score


def test_detect_issuer_transfer_loaded_synthetic() -> None:
    ocr = _ocr(_transfer_loaded_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.INTERFISA
    assert outcome.variant == "transfer_loaded"


def test_familiar_loaded_does_not_match_interfisa_profile() -> None:
    lines = [
        "Transferencia cargada con exito",
        "Monto a enviar",
        "Gs. 50.000",
        "Enviado por",
        "REMITENTE EJEMPLO",
    ]
    result = INTERFISA_TRANSFER_LOADED.evaluate(_ocr(lines), None)
    assert not result.accepted
