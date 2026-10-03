"""Synthetic EKO parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.eko import EkoReceiptParser, EkoVariant
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


def _send_receipt_lines() -> list[str]:
    return [
        "Listo",
        "Envio",
        "Gs 55.000",
        "REMITENTE EJEMPLO UNO",
        "Banco Familiar",
        "Cta. N° ••••••12",
        "DESTINATARIO EJEMPLO DOS",
        "Alias: 7788990",
        "Nota de prueba",
        "Compartir comprobante",
    ]


def _transfer_detail_lines() -> list[str]:
    return [
        "Detalle",
        "Enviaste",
        "Gs 44.000",
        "DESTINATARIO EJEMPLO TRES",
        "Transferencia",
        "Gs 44.000",
        "301112233",
        "01 oct 2026",
        "9000111222",
        "Compartir comprobante",
    ]


def test_send_receipt_parses_sender_and_amount() -> None:
    receipt = EkoReceiptParser().parse_ocr(
        _ocr(_send_receipt_lines()),
        variant=EkoVariant.SEND_RECEIPT,
    )
    assert receipt.issuer == Issuer.EKO
    assert receipt.amount == Decimal("55000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO UNO"
    assert receipt.sender.bank == "Banco Familiar"
    assert receipt.sender.masked_account == "••••••12"
    assert receipt.recipient is not None
    assert receipt.recipient.alias == "7788990"
    assert receipt.concept == "Nota de prueba"


def test_transfer_detail_parses_amount_without_sender() -> None:
    receipt = EkoReceiptParser().parse_ocr(
        _ocr(_transfer_detail_lines()),
        variant=EkoVariant.TRANSFER_DETAIL,
    )
    assert receipt.amount == Decimal("44000")
    assert receipt.sender is None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO TRES"
    assert receipt.recipient.account == "301112233"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.year == 2026
    assert receipt.transaction_identifiers[0].value == "9000111222"
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.TICKET


def test_registry_exposes_eko_parser() -> None:
    assert parser_for_issuer(Issuer.EKO.value) is not None


def test_variant_inference_requires_structure() -> None:
    with pytest.raises(ParseError, match="Could not infer"):
        EkoReceiptParser().parse_ocr(_ocr(["Detalle", "Gs 1.000"]))
