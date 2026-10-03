"""Synthetic Vaquita issuer detection tests."""

from __future__ import annotations

from PIL import Image

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.vaquita import VAQUITA_YELLOW_TRANSFER
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


def _comprobante_lines() -> list[str]:
    return [
        "Comprobante de proceso",
        "Enviado a: DESTINATARIO EJEMPLO",
        "Entidad: BANCO EJEMPLO S.A.",
        "Monto: Gs. 10.000",
        "Motivo: Ejemplo",
        "Vaquita",
    ]


def _yellow_header_image() -> Image.Image:
    return Image.new("RGB", (400, 800), (240, 205, 40))


def test_vaquita_yellow_transfer_profile_accepts_synthetic_receipt() -> None:
    ocr = _ocr(_comprobante_lines())
    result = VAQUITA_YELLOW_TRANSFER.evaluate(ocr, _yellow_header_image())
    assert result.accepted
    assert result.score >= VAQUITA_YELLOW_TRANSFER.min_score


def test_detect_issuer_comprobante_synthetic() -> None:
    ocr = _ocr(_comprobante_lines())
    outcome = detect_issuer_from_ocr(ocr, image=_yellow_header_image())
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.VAQUITA
    assert outcome.variant == "yellow_transfer"
