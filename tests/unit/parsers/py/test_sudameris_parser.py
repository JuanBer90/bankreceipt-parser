"""Synthetic Sudameris parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.sudameris import SudamerisReceiptParser, SudamerisVariant
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


def _transfer_receipt_lines() -> list[str]:
    return [
        "SUDAMERIS",
        "¡Transferencia exitosa!",
        "Transferencia Bancaria",
        "Gs. 88.000",
        "Enviado por",
        "APELLIDO EJEMPLO, NOMBRE EJEMPLO",
        "....529000 Caja de Ahorros",
        "Enviado a",
        "DESTINATARIO EJEMPLO UNO",
        "301112233 BANCO EJEMPLO S.A.",
        "30/09/2026 - 16:09:43",
        "Número de Soporte",
        "0093000001",
    ]


def test_transfer_receipt_parses_amount_sender_and_recipient() -> None:
    receipt = SudamerisReceiptParser().parse_ocr(
        _ocr(_transfer_receipt_lines()),
        variant=SudamerisVariant.TRANSFER_RECEIPT,
    )
    assert receipt.issuer == Issuer.SUDAMERIS
    assert receipt.amount == Decimal("88000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.sender is not None
    assert receipt.sender.name == "NOMBRE EJEMPLO APELLIDO EJEMPLO"
    assert receipt.sender.bank is None
    assert receipt.sender.masked_account == "....529000"
    assert receipt.sender.account_type == AccountType.SAVINGS
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    assert receipt.recipient.account == "301112233"
    assert receipt.recipient.bank == "BANCO EJEMPLO S.A."
    assert len(receipt.transaction_identifiers) == 1
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.OPERATION
    assert receipt.transaction_identifiers[0].value == "0093000001"


def test_registry_resolves_sudameris_parser() -> None:
    parser = parser_for_issuer(Issuer.SUDAMERIS.value)
    assert parser is not None
    assert parser.issuer == Issuer.SUDAMERIS


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        SudamerisReceiptParser().parse_ocr(_ocr(_transfer_receipt_lines()), variant="unknown")
