"""Issuer detection heuristic tests (synthetic OCR only)."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.signals import score_text_signals
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _line(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.8, height=0.04),
        line_index=1,
    )


def test_score_text_signals_prefers_header_placement() -> None:
    ocr = OCRResult(
        text="UENO\nComprobante de transferencia",
        image_width=1000,
        image_height=2000,
        elements=[
            _line("UENO", 0.05),
            _line("Comprobante de transferencia", 0.2),
        ],
    )
    hits = score_text_signals(ocr)
    assert hits
    assert hits[0].issuer_key == Issuer.UENO
    assert hits[0].score >= 1.5


def test_detect_unknown_on_ambiguous_signals() -> None:
    ocr = OCRResult(
        text="ITAU\nUENO\nComprobante",
        image_width=1000,
        image_height=2000,
        elements=[
            _line("ITAU", 0.05),
            _line("UENO", 0.06),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.UNKNOWN


def test_detect_identified_when_clear_ueno_signal() -> None:
    ocr = OCRResult(
        text="UENO Bank\nComprobante de transferencia",
        image_width=1000,
        image_height=2000,
        elements=[
            _line("UENO Bank", 0.05),
            _line("Comprobante de transferencia", 0.15),
            _line("Monto", 0.4),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.UENO


def test_aliases_in_counterparty_text_do_not_outweigh_header_issuer() -> None:
    """Alias variants are one issuer clue, not independent corroboration."""
    ocr = OCRResult(
        text="Sudameris\nFamiliar Banco Familiar\nComprobante",
        image_width=1000,
        image_height=2000,
        elements=[
            _line("Sudameris", 0.05),
            _line("Familiar", 0.55),
            _line("Banco Familiar", 0.60),
        ],
    )

    outcome = detect_issuer_from_ocr(ocr)

    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == "sudameris"
