"""Synthetic INTERFISA parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.interfisa import InterfisaReceiptParser, InterfisaVariant
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


def test_transfer_loaded_parses_amount_and_sender() -> None:
    receipt = InterfisaReceiptParser().parse_ocr(
        _ocr(_transfer_loaded_lines()),
        variant=InterfisaVariant.TRANSFER_LOADED,
    )
    assert receipt.issuer == Issuer.INTERFISA
    assert receipt.amount == Decimal("88500")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.sender is not None
    assert receipt.sender.name == "NOMBRE EJEMPLO APELLIDO EJEMPLO"
    assert receipt.sender.account == "800011122"
    assert receipt.concept == "Pago servicios ejemplo"
    assert receipt.recipient is not None
    assert receipt.recipient.account == "900099988"
    assert receipt.recipient.bank == "BANCO DESTINO S.A.E."
    assert receipt.recipient.document_identifier == "1234567"


def test_registry_exposes_interfisa_parser() -> None:
    parser = parser_for_issuer(Issuer.INTERFISA.value)
    assert parser is not None
    assert parser.issuer == Issuer.INTERFISA


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        InterfisaReceiptParser().parse_ocr(_ocr(_transfer_loaded_lines()), variant="unknown")


def test_transaction_identifier_kind() -> None:
    receipt = InterfisaReceiptParser().parse_ocr(
        _ocr(_transfer_loaded_lines()),
        variant=InterfisaVariant.TRANSFER_LOADED,
    )
    assert len(receipt.transaction_identifiers) == 1
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.OPERATION
