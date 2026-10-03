"""Synthetic Medalla Milagrosa parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.medalla_milagrosa import (
    MedallaMilagrosaReceiptParser,
    MedallaMilagrosaVariant,
)
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


def _transfer_operation_lines() -> list[str]:
    return [
        "Transferencia en proceso :)",
        "Gs. 12.500",
        "De",
        "APELLIDO UNO, NOMBRE EJEMPLO",
        "Cuenta N° 1002003",
        "Para",
        "DESTINATARIO EJEMPLO DOS",
        "BANCO EJEMPLO S.A.",
        "Cuenta N° 301112233",
        "Detalles",
        "Concepto Pago ejemplo",
        "Fecha y Hora 01 oct. 2026, 3:15:00 p.m.",
        "N° de comprobante 202610011515009999",
        "Tipo Transferencia SIPAP",
        "sip",
    ]


def test_registry_exposes_medalla_parser() -> None:
    parser = parser_for_issuer(Issuer.MEDALLA_MILAGROSA.value)
    assert parser is not None
    assert parser.issuer == Issuer.MEDALLA_MILAGROSA


def test_transfer_operation_parses_amount_and_sender_name() -> None:
    receipt = MedallaMilagrosaReceiptParser().parse_ocr(
        _ocr(_transfer_operation_lines()),
        variant=MedallaMilagrosaVariant.TRANSFER_OPERATION,
    )
    assert receipt.issuer == Issuer.MEDALLA_MILAGROSA
    assert receipt.amount == Decimal("12500")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.PENDING
    assert receipt.sender is not None
    assert receipt.sender.name == "NOMBRE EJEMPLO APELLIDO UNO"
    assert receipt.sender.account == "1002003"
    assert receipt.sender.bank is None
    assert receipt.payment_network == "SIP"
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.OPERATION
    assert receipt.transaction_identifiers[0].value == "202610011515009999"


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        MedallaMilagrosaReceiptParser().parse_ocr(
            _ocr(_transfer_operation_lines()),
            variant="unknown_layout",
        )
