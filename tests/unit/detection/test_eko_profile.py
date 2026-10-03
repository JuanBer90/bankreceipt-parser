"""EKO detection profile tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.profiles.py.eko import EKO_SEND_RECEIPT, EKO_TRANSFER_DETAIL
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
        image_height=900,
        elements=[_el(text, y) for text, y in lines],
    )


def test_send_receipt_profile_accepts_listo_envio_layout() -> None:
    result = EKO_SEND_RECEIPT.evaluate(
        _ocr(
            [
                ("Listo", 0.1),
                ("Envio", 0.2),
                ("Compartir comprobante", 0.8),
            ]
        ),
        None,
    )
    assert result.accepted


def test_transfer_detail_profile_accepts_detalle_layout() -> None:
    result = EKO_TRANSFER_DETAIL.evaluate(
        _ocr(
            [
                ("Detalle", 0.05),
                ("Enviaste", 0.12),
                ("Transferencia", 0.3),
                ("Compartir comprobante", 0.7),
            ]
        ),
        None,
    )
    assert result.accepted


def test_detect_eko_send_receipt_variant() -> None:
    outcome = detect_issuer_from_ocr(
        _ocr(
            [
                ("Listo", 0.1),
                ("Envio", 0.2),
                ("Compartir comprobante", 0.8),
            ]
        )
    )
    assert outcome.issuer == "eko"
    assert outcome.variant == "send_receipt"
