"""Synthetic BNF issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.profiles.py.bnf import (
    BNF_OPERATION_SUCCESS_RECEIPT,
    BNF_TRANSFER_SENT_CARD,
)
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


def _transfer_sent_card_lines(*, include_solar: bool = False) -> list[tuple[str, float]]:
    lines: list[tuple[str, float]] = [
        ("Transferencia Enviada", 0.08),
        ("Destinatario", 0.30),
        ("JANE DOE", 0.34),
        ("Cuenta destino", 0.38),
        ("301112233", 0.42),
        ("Entidad destino", 0.46),
    ]
    if include_solar:
        lines.append(("SOLAR BANCO S.A.E.", 0.50))
    else:
        lines.append(("BANCO EJEMPLO S.A.", 0.50))
    lines.extend(
        [
            ("Monto", 0.54),
            ("GS. 20.000", 0.58),
            ("Moneda", 0.62),
            ("GUARANIES", 0.66),
            ("Cuenta origen", 0.70),
            ("000-99-0888777", 0.74),
            ("Tipo de cuenta", 0.78),
            ("Caja de Ahorro", 0.82),
            ("Fecha y hora", 0.86),
            ("30/09/2026 - 20:47", 0.90),
            ("Nro. de Comprobante", 0.94),
            ("3899901", 0.96),
        ]
    )
    return lines


def _operation_success_lines(*, bnf_line: str = "SIP BNF") -> list[tuple[str, float]]:
    return [
        ("¡Operación Exitosa!", 0.06),
        (bnf_line, 0.10),
        ("Fecha de Operación 2026-10-01 15:37:33", 0.18),
        ("Nro. Comprobante: 4107700", 0.26),
        (
            "Detalle: Transferencia a Cuentas de otros Bancos - SIP",
            0.34,
        ),
        ("Enviado por: PELOZO EJEMPLO, REMITENTE TRES", 0.42),
        ("Cuenta destino: DESTINATARIO DEMO", 0.50),
        ("301112233", 0.54),
        ("Banco/Cooperativa: SOLAR BANCO S.A.E.", 0.62),
        ("Monto: Gs 70.000", 0.70),
        ("Concepto: .", 0.78),
    ]


def test_operation_success_explicit_bnf_variant() -> None:
    outcome = detect_issuer_from_ocr(_ocr(_operation_success_lines()))
    assert outcome.issuer == Issuer.BNF
    assert outcome.variant == "operation_success_receipt"


def test_sip_curly_quote_bnf_lexicon_and_variant() -> None:
    ocr = _ocr(_operation_success_lines(bnf_line='SIP “BNF'))
    hits = score_text_signals(ocr)
    assert any(hit.issuer_key == Issuer.BNF.value for hit in hits)
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer == Issuer.BNF
    assert outcome.variant == "operation_success_receipt"


def test_transfer_sent_card_self_establishing_without_bnf_text() -> None:
    ocr = _ocr(_transfer_sent_card_lines())
    assert "bnf" not in ocr.text.casefold()
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer == Issuer.BNF
    assert outcome.variant == "transfer_sent_card"


def test_partial_generic_labels_do_not_accept_bnf() -> None:
    ocr = _ocr(
        [
            ("Cuenta destino", 0.40),
            ("Monto", 0.50),
            ("Cuenta origen", 0.60),
        ]
    )
    assert BNF_TRANSFER_SENT_CARD.evaluate(ocr, None).accepted is False
    assert BNF_OPERATION_SUCCESS_RECEIPT.evaluate(ocr, None).accepted is False


def test_solar_destination_does_not_drive_issuer_lexicon() -> None:
    ocr = _ocr(_transfer_sent_card_lines(include_solar=True))
    hits = score_text_signals(ocr)
    assert not any(hit.issuer_key == "solar" for hit in hits)
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer == Issuer.BNF
    assert outcome.variant == "transfer_sent_card"


def test_transfer_sent_card_required_signal_missing() -> None:
    lines = _transfer_sent_card_lines()
    lines = [item for item in lines if item[0] != "Entidad destino"]
    result = BNF_TRANSFER_SENT_CARD.evaluate(_ocr(lines), None)
    assert not result.accepted
    assert "entidad_destino_label" in result.required_signals_missing


def test_two_bnf_variants_are_distinct() -> None:
    card = detect_issuer_from_ocr(_ocr(_transfer_sent_card_lines()))
    receipt = detect_issuer_from_ocr(_ocr(_operation_success_lines()))
    assert card.issuer == receipt.issuer == Issuer.BNF
    assert card.variant == "transfer_sent_card"
    assert receipt.variant == "operation_success_receipt"
    assert card.variant != receipt.variant
