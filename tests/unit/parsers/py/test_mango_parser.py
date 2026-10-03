"""Synthetic Mango parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.mango import MangoReceiptParser, MangoVariant
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


def _sip_detail_lines() -> list[str]:
    return [
        "Detalle",
        "Transferencia SIP",
        "Enviaste",
        "Gs. 88.000",
        "DESTINATARIO EJEMPLO UNO",
        "BANCO EJEMPLO S.A.",
        "Cta. N° 301112233",
        "Origen REMITENTE EJEMPLO DOS",
        "TU FINANCIERA",
        "Cta. N° .....529",
        "Fecha y hora 01 oct 2026 - 14:53 Hs",
        "Transacción N° 9000111222",
        "Estado Transferencia enviada",
    ]


def _transfer_receipt_lines() -> list[str]:
    return [
        "Monto",
        "Gs. 22.000",
        "DESTINATARIO EJEMPLO TRES",
        "BANCO EJEMPLO S.A.",
        "Cta. N° 301112233",
        "Origen REMITENTE EJEMPLO CUATRO",
        "TU FINANCIERA",
        "Cta. N° .....487",
        "Fecha y hora 01 oct 2026 - 12:18 Hs",
        "Transacción N° aabbccdd00112233",
        "Estado Procesando transferencia",
    ]


def test_sip_detail_parses_sender_amount_and_network() -> None:
    receipt = MangoReceiptParser().parse_ocr(
        _ocr(_sip_detail_lines()),
        variant=MangoVariant.SIP_DETAIL,
    )
    assert receipt.issuer == Issuer.MANGO
    assert receipt.amount == Decimal("88000")
    assert receipt.currency == "PYG"
    assert receipt.payment_network == "SIP"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO DOS"
    assert receipt.sender.bank is None
    assert receipt.sender.masked_account == ".....529"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    assert receipt.recipient.account == "301112233"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.hour == 14
    assert receipt.transaction_identifiers[0].value == "9000111222"
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.OPERATION


def test_transfer_receipt_parses_pending_status() -> None:
    receipt = MangoReceiptParser().parse_ocr(
        _ocr(_transfer_receipt_lines()),
        variant=MangoVariant.TRANSFER_RECEIPT,
    )
    assert receipt.amount == Decimal("22000")
    assert receipt.status == TransferStatus.PENDING
    assert receipt.raw_status == "Procesando transferencia"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO CUATRO"
    assert receipt.sender.bank is None
    assert receipt.payment_network is None


def test_registry_exposes_mango_parser() -> None:
    assert parser_for_issuer(Issuer.MANGO.value) is not None


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        MangoReceiptParser().parse_ocr(_ocr(_sip_detail_lines()), variant="unknown_layout")
