"""Synthetic Atlas issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.matcher import evaluate_profiles
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles import ALL_PROFILES
from bankreceipt_parser.detection.profiles.py.atlas import ATLAS_TRANSFER_RECEIPT
from bankreceipt_parser.detection.profiles.py.bnf import BNF_TRANSFER_SENT_CARD
from bankreceipt_parser.detection.signals.product_lexicon import score_text_signals
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float, x: float = 0.2) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=x, y=y, width=0.5, height=0.03),
        line_index=int(y * 100),
    )


def _ocr(lines: list[tuple[str, float]]) -> OCRResult:
    return OCRResult(
        text="\n".join(text for text, _ in lines),
        image_width=400,
        image_height=900,
        elements=[_el(text, y) for text, y in lines],
    )


def _sample1_lines() -> list[tuple[str, float]]:
    return [
        ("SIP / BANCO ATLAS", 0.06),
        ("¡Transferencia enviada!", 0.35),
        ("Información de la transferencia", 0.40),
        ("Nro. de Operación: 2610099888777", 0.44),
        ("Ref. Externa: BNITPYPAARES261009900112200015268999", 0.48),
        ("Remitente: REMITENTE EJEMPLO UNO", 0.52),
        ("Cuenta Origen: CC | 1271001", 0.56),
        ("Destinatario", 0.60),
        ("Beneficiario: DESTINATARIO EJEMPLO UNO", 0.64),
        ("Cuenta Destino: 301112233", 0.68),
        ("Entidad Destino: SOLAR BANCO (24/7)", 0.72),
        ("Monto Débito GS: 20.000", 0.76),
        ("Fecha y Hora de Operación: 01/10/2026 - 13:05 Hs", 0.80),
    ]


def _sample2_lines() -> list[tuple[str, float]]:
    return [
        ("Sip E BANCO", 0.04),
        ("SIP | BA ATLAS", 0.08),
        ("¡Transferencia enviada!", 0.35),
        ("Información de latransferencia", 0.40),
        ("Nro. de Operación:.2609000111222", 0.44),
        ("Remitente: REMITENTE EJEMPLO DOS", 0.52),
        ("Cuenta Origen: AH | 1322002", 0.56),
        ("Beneficiario: DESTINATARIO EJEMPLO", 0.64),
        ("UNO", 0.66),
        ("Cuenta Destino: 301112233", 0.68),
        ("Entidad Destino: SOLAR BANCO (24/7)", 0.72),
        ("Monto Débito GS: 80.000", 0.76),
        ("Fecha y Hora de Operación: 30/09/2026 - 20:28", 0.80),
        ("Hs", 0.82),
    ]


def test_atlas_transfer_receipt_profile_accepts_sample1() -> None:
    ocr = _ocr(_sample1_lines())
    result = ATLAS_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted
    assert result.score >= ATLAS_TRANSFER_RECEIPT.min_score


def test_atlas_transfer_receipt_profile_accepts_sample2() -> None:
    ocr = _ocr(_sample2_lines())
    result = ATLAS_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted


def test_detect_issuer_from_ocr_sample1() -> None:
    ocr = _ocr(_sample1_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == "atlas"
    assert outcome.variant == "transfer_receipt"


def test_detect_issuer_from_ocr_sample2() -> None:
    ocr = _ocr(_sample2_lines())
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == "atlas"
    assert outcome.variant == "transfer_receipt"


def test_atlas_lexicon_hit_from_banco_atlas() -> None:
    ocr = _ocr(_sample1_lines())
    hits = score_text_signals(ocr)
    atlas_hits = [h for h in hits if h.issuer_key == Issuer.ATLAS.value]
    assert atlas_hits
    assert any("atlas" in h.matched_term.casefold() for h in atlas_hits)


def test_bnf_profile_may_score_higher_but_issuer_stays_atlas() -> None:
    ocr = _ocr(_sample1_lines())
    profiles = evaluate_profiles(ocr, None, ALL_PROFILES)
    bnf = next(r for r in profiles if r.variant == BNF_TRANSFER_SENT_CARD.variant)
    atlas = next(r for r in profiles if r.variant == ATLAS_TRANSFER_RECEIPT.variant)
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer == "atlas"
    if bnf.score > atlas.score:
        assert any(c.issuer == "bnf:transfer_sent_card" for c in outcome.candidates)


def test_solar_destination_does_not_drive_atlas_issuer_lexicon() -> None:
    ocr = _ocr(_sample1_lines())
    hits = score_text_signals(ocr)
    assert not any(hit.issuer_key == "solar" for hit in hits)
