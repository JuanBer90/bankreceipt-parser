"""Synthetic ECLUB parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.eclub import EclubReceiptParser, EclubVariant
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


def _transfer_screen_lines() -> list[str]:
    return [
        "Transferencia Realizada",
        "Monto Gs 88.000",
        "Estado Pendiente",
        "Fecha y hora 12/11/2026 09:15",
        "Beneficiario",
        "Nro Cuenta 445566778",
        "Entidad ENTIDAD DESTINO SA",
        "Titular DESTINATARIO EJEMPLO",
        "UNO",
        "Remitente",
        "Titular REMITENTE EJEMPLO DOS",
        "Cuenta 112233445",
    ]


def test_transfer_screen_parses_core_fields() -> None:
    receipt = EclubReceiptParser().parse_ocr(
        _ocr(_transfer_screen_lines()),
        variant=EclubVariant.TRANSFER_SCREEN,
    )
    assert receipt.issuer == Issuer.ECLUB
    assert receipt.amount == Decimal("88000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.PENDING
    assert receipt.raw_status == "Pendiente"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-11-12T09:15:00"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO DOS"
    assert receipt.sender.account == "112233445"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    assert receipt.recipient.bank == "ENTIDAD DESTINO SA"
    assert receipt.recipient.account == "445566778"


def test_registry_exposes_eclub_parser() -> None:
    parser = parser_for_issuer(Issuer.ECLUB.value)
    assert parser is not None
    assert parser.issuer == Issuer.ECLUB


def test_variant_inference_requires_beneficiario_and_remitente() -> None:
    with pytest.raises(ParseError, match="Could not infer"):
        EclubReceiptParser().parse_ocr(_ocr(["Transferencia Realizada", "Monto Gs 1.000"]))
