"""Synthetic ZETA issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.issuer_resolution import resolve_issuer
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


def _zetabonco_header_ocr() -> OCRResult:
    """Layout like preprocessed ZETA header: glued zetabonco, no standalone zeta token."""
    elements = [
        _el("@ zetabonco", 0.05),
        _el("COMPROBANTE", 0.10),
        _el("TRANSFERENCIA ENVIADA", 0.18),
        _el("NRO. COMPROBANTE: 880011223344", 0.28),
        _el("GS. 88.000", 0.35),
        _el("CONCEPTO NOTA EJEMPLO", 0.45),
        _el("Compartir comprobante", 0.82),
    ]
    text = "\n".join(el.text for el in elements)
    return OCRResult(text=text, image_width=400, image_height=900, elements=elements)


def test_resolve_issuer_from_zetabonco_header_without_standalone_zeta() -> None:
    ocr = _zetabonco_header_ocr()
    resolution = resolve_issuer(ocr)
    assert resolution is not None
    assert resolution.issuer == Issuer.ZETA.value
    assert resolution.score >= 1.2
    assert any(hit.matched_term == "zetabonco" for hit in resolution.hits)


def test_detect_issuer_zetabonco_header_transfer_receipt() -> None:
    ocr = _zetabonco_header_ocr()
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.ZETA
    assert outcome.variant == "transfer_receipt"
