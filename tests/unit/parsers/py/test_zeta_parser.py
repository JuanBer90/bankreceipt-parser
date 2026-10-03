"""Synthetic ZETA parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.zeta import ZetaReceiptParser, ZetaVariant
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
        "zeta banco",
        "COMPROBANTE",
        "TRANSFERENCIA ENVIADA",
        "NRO. COMPROBANTE: 880011223344",
        "GS. 88.000",
        "CONCEPTO",
        "NOTA EJEMPLO UNO",
        "15/03/2026 - 09:40:12",
        "PARA",
        "RECIPIENTE EJEMPLO DOS",
        "ENTIDAD",
        "BANCO DESTINO S.A.",
        "NRO. DE CUENTA",
        "301112233",
        "DESDE",
        "REMITENTE EJEMPLO TRES",
        "ENTIDAD",
        "ZETA BANCO",
        "NRO. DE CUENTA",
        "1998877665",
        "sip",
        "Compartir",
    ]


def test_transfer_receipt_parses_amount_and_sender() -> None:
    receipt = ZetaReceiptParser().parse_ocr(
        _ocr(_transfer_receipt_lines()),
        variant=ZetaVariant.TRANSFER_RECEIPT,
    )
    assert receipt.issuer == Issuer.ZETA
    assert receipt.amount == Decimal("88000")
    assert receipt.currency == "PYG"
    assert receipt.payment_network == "SIP"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "TRANSFERENCIA ENVIADA"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO TRES"
    assert receipt.sender.bank == "ZETA BANCO"
    assert receipt.sender.account == "1998877665"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "RECIPIENTE EJEMPLO DOS"
    assert receipt.recipient.bank == "BANCO DESTINO S.A."
    assert receipt.recipient.account == "301112233"
    assert receipt.concept == "NOTA EJEMPLO UNO"
    assert receipt.transaction_identifiers
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.OPERATION
    assert receipt.transaction_identifiers[0].value == "880011223344"


def test_sender_name_normalizes_single_comma_layout() -> None:
    lines = _transfer_receipt_lines()
    lines[15] = "APELLIDO EJEMPLO, NOMBRE EJEMPLO CUATRO"
    receipt = ZetaReceiptParser().parse_ocr(_ocr(lines), variant=ZetaVariant.TRANSFER_RECEIPT)
    assert receipt.sender is not None
    assert receipt.sender.name == "NOMBRE EJEMPLO CUATRO APELLIDO EJEMPLO"


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        ZetaReceiptParser().parse_ocr(_ocr(_transfer_receipt_lines()), variant="other_layout")


def test_registry_exposes_zeta_parser() -> None:
    parser = parser_for_issuer(Issuer.ZETA.value)
    assert parser is not None
    assert parser.issuer == Issuer.ZETA
