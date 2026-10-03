"""Synthetic FINANCIERA PYJ parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.financiera_pyj import (
    FinancieraPyjReceiptParser,
    FinancieraPyjVariant,
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


def _transfer_receipt_lines() -> list[str]:
    return [
        "Fecha: 01/11/2026 Hora: 10:30",
        "FINANCIERA",
        "Comprobante de Transferencia",
        "Nro. Transacción: 900011122",
        "Cuenta débito: 123456",
        "Nombre del Titular REMITENTE EJEMPLO UNO",
        "Beneficiario: RECIPIENTE EJEMPLO DOS",
        "Cuenta Credito: 900033344455",
        "Entidad Destino: BANCO DESTINO S.A.",
        "Detalle: ........",
        "NTR: FIPJPYPAARES011126001",
        "Gs. 55.000",
    ]


def test_transfer_receipt_parses_amount_and_sender() -> None:
    receipt = FinancieraPyjReceiptParser().parse_ocr(
        _ocr(_transfer_receipt_lines()),
        variant=FinancieraPyjVariant.TRANSFER_RECEIPT,
    )
    assert receipt.issuer == Issuer.FINANCIERA_PYJ
    assert receipt.amount == Decimal("55000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO UNO"
    assert receipt.sender.account == "123456"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "RECIPIENTE EJEMPLO DOS"
    assert receipt.recipient.account == "900033344455"
    assert receipt.recipient.bank == "BANCO DESTINO S.A."
    assert receipt.concept is None
    kinds = {item.kind for item in receipt.transaction_identifiers}
    assert TransactionIdentifierKind.OPERATION in kinds
    assert TransactionIdentifierKind.REFERENCE in kinds


def test_sender_name_normalizes_single_comma_layout() -> None:
    lines = _transfer_receipt_lines()
    lines[5] = "Nombre del Titular APELLIDO EJEMPLO, NOMBRE EJEMPLO TRES"
    receipt = FinancieraPyjReceiptParser().parse_ocr(
        _ocr(lines),
        variant=FinancieraPyjVariant.TRANSFER_RECEIPT,
    )
    assert receipt.sender is not None
    assert receipt.sender.name == "NOMBRE EJEMPLO TRES APELLIDO EJEMPLO"


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        FinancieraPyjReceiptParser().parse_ocr(
            _ocr(_transfer_receipt_lines()),
            variant="other_layout",
        )


def test_registry_exposes_financiera_pyj_parser() -> None:
    parser = parser_for_issuer(Issuer.FINANCIERA_PYJ.value)
    assert parser is not None
    assert parser.issuer == Issuer.FINANCIERA_PYJ
