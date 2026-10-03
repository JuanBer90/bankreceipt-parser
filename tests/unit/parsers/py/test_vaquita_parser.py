"""Synthetic Vaquita parser tests (invented data only)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.vaquita import VaquitaReceiptParser, VaquitaVariant
from bankreceipt_parser.parsers.registry import parser_for_issuer


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


def _yellow_transfer_lines() -> list[str]:
    return [
        "Comprobante de proceso",
        "Enviado a: DESTINATARIO EJEMPLO UNO",
        "Entidad: BANCO EJEMPLO S.A.",
        "Cta: 301112233",
        "CI: 1234567",
        "Fecha: 01 de octubre de 2026 a las 14:30",
        "Monto: Gs. 88.000",
        "Motivo: Servicio ejemplo",
        "Importante:",
        "La transferencia está en proceso. Favor verificar su recepción con la entidad receptora.",
        "Con el respaldo de Finlatina S.A. de Finanzas",
        "Visitá nuestra web: www.vaquita.com.py",
    ]


def test_yellow_transfer_parses_recipient_amount_and_pending_status() -> None:
    receipt = VaquitaReceiptParser().parse_ocr(
        _ocr(_yellow_transfer_lines()),
        variant=VaquitaVariant.YELLOW_TRANSFER,
    )
    assert receipt.issuer == Issuer.VAQUITA
    assert receipt.amount == Decimal("88000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.PENDING
    assert receipt.payment_network is None
    assert receipt.sender is None
    assert receipt.occurred_at == datetime(2026, 10, 1, 14, 30)
    assert receipt.concept == "Servicio ejemplo"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    assert receipt.recipient.bank == "BANCO EJEMPLO S.A."
    assert receipt.recipient.account == "301112233"
    assert receipt.recipient.document_identifier == "1234567"


def test_comma_sender_name_on_recipient_label_is_normalized() -> None:
    lines = _yellow_transfer_lines()
    lines[1] = "Enviado a: APELLIDO EJEMPLO, NOMBRE EJEMPLO"
    receipt = VaquitaReceiptParser().parse_ocr(_ocr(lines), variant=VaquitaVariant.YELLOW_TRANSFER)
    assert receipt.recipient is not None
    assert receipt.recipient.name == "NOMBRE EJEMPLO APELLIDO EJEMPLO"


def test_registry_exposes_vaquita_parser() -> None:
    parser = parser_for_issuer(Issuer.VAQUITA.value)
    assert parser is not None
    assert parser.issuer == Issuer.VAQUITA


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError, match="Unsupported Vaquita"):
        VaquitaReceiptParser().parse_ocr(_ocr(_yellow_transfer_lines()), variant="unknown_layout")
