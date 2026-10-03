"""Synthetic BASA parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.basa import BasaReceiptParser, BasaVariant
from bankreceipt_parser.parsers.registry import parser_for_issuer


def _el(text: str, y: float, x: float = 0.25) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=x, y=y, width=0.3, height=0.03),
        line_index=int(y * 100),
    )


def _ocr(lines: list[str]) -> OCRResult:
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=[_el(line, 0.05 + index * 0.04) for index, line in enumerate(lines)],
    )


def _transfer_success_lines() -> list[str]:
    return [
        "Transferencia exitosa",
        "DESTINATARIO EJEMPLO UNO",
        "Alias CI: 4455667",
        "Entidad Destino S.A. - AH-887766554",
        "Monto",
        "Gs. 99.500",
        "Fecha",
        "Hoy a las 14:10",
        "Compartir comprobante",
    ]


def _party_cards_lines() -> list[str]:
    return [
        "Transferencia exitosa",
        "Gs. 55.000",
        "REMITENTE EJEMPLO DOS",
        "Banco Basa - AH-112233445",
        "DESTINATARIO EJEMPLO TRES",
        "Cooperativa Destino - AH-998877665",
        "Comprobante: 70001234",
        "Realizado el: 10/08/2026 a las 11:22",
    ]


def test_transfer_success_parses_labeled_layout() -> None:
    receipt = BasaReceiptParser().parse_ocr(
        _ocr(_transfer_success_lines()),
        variant=BasaVariant.TRANSFER_SUCCESS,
    )
    assert receipt.issuer == Issuer.BASA
    assert receipt.amount == Decimal("99500")
    assert receipt.currency == "PYG"
    assert receipt.sender is None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    assert receipt.recipient.bank == "Entidad Destino S.A."
    assert receipt.recipient.account == "887766554"
    assert receipt.recipient.account_type == AccountType.SAVINGS
    assert receipt.recipient.alias == "4455667"
    assert receipt.occurred_at is None
    assert receipt.status == TransferStatus.COMPLETED


def test_party_cards_parses_sender_and_amount() -> None:
    receipt = BasaReceiptParser().parse_ocr(
        _ocr(_party_cards_lines()),
        variant=BasaVariant.PARTY_CARDS,
    )
    assert receipt.amount == Decimal("55000")
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO DOS"
    assert receipt.sender.bank == "Banco Basa"
    assert receipt.sender.account == "112233445"
    assert receipt.recipient is not None
    assert receipt.recipient.account == "998877665"
    assert len(receipt.transaction_identifiers) == 1
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.TICKET
    assert receipt.transaction_identifiers[0].value == "70001234"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-08-10T11:22:00"


def test_registry_exposes_basa_parser() -> None:
    parser = parser_for_issuer(Issuer.BASA.value)
    assert parser is not None
    assert parser.issuer == Issuer.BASA


def test_variant_inference_requires_success_copy() -> None:
    with pytest.raises(ParseError, match="Could not infer"):
        BasaReceiptParser().parse_ocr(_ocr(["Banco Basa", "Gs. 1.000"]))
