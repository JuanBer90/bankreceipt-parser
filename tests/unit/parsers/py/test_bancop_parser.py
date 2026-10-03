"""Synthetic BANCOP parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.bancop import BancopReceiptParser, BancopVariant
from bankreceipt_parser.parsers.registry import parser_for_issuer


def _el(text: str, x: float, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=x, y=y, width=0.1, height=0.02),
        line_index=int(y * 100),
    )


def _transfer_screen_ocr(lines: list[str], destino_elements: list[OCRTextElement]) -> OCRResult:
    base_elements = [_el(line, 0.1, 0.05 + index * 0.04) for index, line in enumerate(lines)]
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=base_elements + destino_elements,
    )


def _transfer_screen_lines() -> list[str]:
    return [
        "Transferencias",
        "Operacion realizada",
        "Ref: 88001234",
        "Origen",
        "REMITENTE EJEMPLO TRES",
        "Cuentas Corrientes N° 0199887766 | Gs.",
        "Destino",
        "Nombre y Apellido Entidad Beneficiaria",
        "Nro. de cuenta",
        "556677889 | Gs.",
        "Tipo de Alias Alias",
        "CI 1122334",
        "Monto Concepto",
        "Gs. 120.500 PAGO",
        "Nro. de comprobante Fecha y hora",
        "88001234 15/12/2026 - 10:20",
        "Compartir comprobante",
    ]


def _destino_column_elements() -> list[OCRTextElement]:
    """Two-column destino row: name left, bank right (invented layout)."""
    return [
        _el("Destino", 0.1, 0.34),
        _el("Nombre", 0.08, 0.36),
        _el("DESTINATARIO", 0.08, 0.40),
        _el("EJEMPLO", 0.20, 0.40),
        _el("CUATRO", 0.32, 0.40),
        _el("ENTIDAD", 0.60, 0.40),
        _el("DESTINO", 0.72, 0.40),
        _el("S.A.", 0.85, 0.40),
        _el("Nro.", 0.08, 0.46),
    ]


def test_transfer_screen_parses_core_fields() -> None:
    receipt = BancopReceiptParser().parse_ocr(
        _transfer_screen_ocr(_transfer_screen_lines(), _destino_column_elements()),
        variant=BancopVariant.TRANSFER_SCREEN,
    )
    assert receipt.issuer == Issuer.BANCOP
    assert receipt.amount == Decimal("120500")
    assert receipt.currency == "PYG"
    assert receipt.concept == "PAGO"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-12-15T10:20:00"
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.TICKET
    assert receipt.transaction_identifiers[0].value == "88001234"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO TRES"
    assert receipt.sender.account == "0199887766"
    assert receipt.sender.account_type == AccountType.CHECKING
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO CUATRO"
    assert receipt.recipient.bank == "ENTIDAD DESTINO S.A."
    assert receipt.recipient.account == "556677889"
    assert receipt.recipient.alias == "1122334"


def test_registry_exposes_bancop_parser() -> None:
    parser = parser_for_issuer(Issuer.BANCOP.value)
    assert parser is not None
    assert parser.issuer == Issuer.BANCOP


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError, match="Unsupported BANCOP"):
        BancopReceiptParser().parse_ocr(
            _transfer_screen_ocr(_transfer_screen_lines(), []),
            variant="other",
        )
