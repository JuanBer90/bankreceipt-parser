"""Synthetic COMECIPAR parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.comecipar import ComeciparReceiptParser, ComeciparVariant
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


def _transfer_success_lines() -> list[str]:
    return [
        "Transferencia",
        "Transferencia exitosa",
        "Gs.",
        "88.500",
        "AB REMITENTE EJEMPLO UNO",
        "COOP COOMECIPAR LTDA · 881122334",
        "DESTINATARIO EJEMPLO DOS",
        "XY ENTIDAD DESTINO S.A. ·",
        "445566778",
        "1 : 99001122",
        "30/11/2026 a las 14:05:18",
    ]


def test_transfer_success_parses_core_fields() -> None:
    receipt = ComeciparReceiptParser().parse_ocr(
        _ocr(_transfer_success_lines()),
        variant=ComeciparVariant.TRANSFER_SUCCESS,
    )
    assert receipt.issuer == Issuer.COMECIPAR
    assert receipt.amount == Decimal("88500")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "Transferencia exitosa"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-11-30T14:05:18"
    assert len(receipt.transaction_identifiers) == 1
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.TICKET
    assert receipt.transaction_identifiers[0].value == "99001122"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO UNO"
    assert receipt.sender.bank == "COOP COOMECIPAR LTDA"
    assert receipt.sender.account == "881122334"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO DOS"
    assert receipt.recipient.bank == "ENTIDAD DESTINO S.A."
    assert receipt.recipient.account == "445566778"


def test_registry_exposes_comecipar_parser() -> None:
    parser = parser_for_issuer(Issuer.COMECIPAR.value)
    assert parser is not None
    assert parser.issuer == Issuer.COMECIPAR


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError, match="Unsupported COMECIPAR"):
        ComeciparReceiptParser().parse_ocr(
            _ocr(_transfer_success_lines()),
            variant="other",
        )


def test_variant_inference_requires_success_copy_and_brand() -> None:
    with pytest.raises(ParseError, match="Could not infer"):
        ComeciparReceiptParser().parse_ocr(_ocr(["Transferencia exitosa", "Gs.", "1.000"]))
