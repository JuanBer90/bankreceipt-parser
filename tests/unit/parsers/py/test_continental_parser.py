"""Synthetic Continental parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.continental import ContinentalReceiptParser, ContinentalVariant
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
        "continental",
        "Comprobante de transferencia",
        "15/03/2026 - 10:15:30",
        "Detalles",
        "Comprobante 900011122",
        "Concepto SERVICIO",
        "Monto debitado 120.000 GS.",
        "Destino",
        "Nombre RECIPIENTE EJEMPLO UNO",
        "Cuenta 123456789",
        "Entidad BANCO DESTINO SA",
        "Moneda PYG",
        "Origen",
        "Nombre REMITENTE, EJEMPLO DOS",
        "Cuenta **** 4321",
        "Envio realizado por Sip",
    ]


def test_parse_transfer_receipt_core_fields() -> None:
    receipt = ContinentalReceiptParser().parse_ocr(
        _ocr(_transfer_receipt_lines()),
        variant=ContinentalVariant.TRANSFER_RECEIPT,
    )
    assert receipt.issuer == Issuer.CONTINENTAL
    assert receipt.amount == Decimal("120000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status is None
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-03-15T10:15:30"
    assert receipt.concept == "SERVICIO"
    assert receipt.payment_network == "SIP"
    assert len(receipt.transaction_identifiers) == 1
    assert receipt.transaction_identifiers[0].kind == TransactionIdentifierKind.TICKET
    assert receipt.transaction_identifiers[0].value == "900011122"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "RECIPIENTE EJEMPLO UNO"
    assert receipt.recipient.account == "123456789"
    assert receipt.recipient.bank == "BANCO DESTINO SA"
    assert receipt.sender is not None
    assert receipt.sender.name == "EJEMPLO DOS REMITENTE"
    assert receipt.sender.account is None
    assert receipt.sender.masked_account == "**** 4321"


def test_registry_exposes_continental_parser() -> None:
    parser = parser_for_issuer(Issuer.CONTINENTAL.value)
    assert parser is not None
    assert parser.issuer == Issuer.CONTINENTAL


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError, match="Unsupported Continental"):
        ContinentalReceiptParser().parse_ocr(
            _ocr(_transfer_receipt_lines()),
            variant="unknown_variant",
        )


def test_variant_inference_requires_structure() -> None:
    with pytest.raises(ParseError, match="Could not infer"):
        ContinentalReceiptParser().parse_ocr(_ocr(["continental", "Comprobante de transferencia"]))


def test_sender_name_natural_order_real_sample_names() -> None:
    """Origen names from Continental real receipts (apellidos, nombres → natural order)."""
    base = _transfer_receipt_lines()
    nombre_idx = next(i for i, line in enumerate(base) if line.startswith("Nombre REMITENTE"))
    cases = (
        ("APELLIDO EJ, PERSONA UNO", "PERSONA UNO APELLIDO EJ"),
        ("OVIEDO EJ, CLIENTE DOS", "CLIENTE DOS OVIEDO EJ"),
    )
    parser = ContinentalReceiptParser()
    for raw, expected in cases:
        lines = list(base)
        lines[nombre_idx] = f"Nombre {raw}"
        receipt = parser.parse_ocr(_ocr(lines), variant=ContinentalVariant.TRANSFER_RECEIPT)
        assert receipt.sender is not None
        assert receipt.sender.name == expected


def test_sender_cuenta_without_mask_chars_stays_empty() -> None:
    """Real Continental OCR often omits ``*``; do not invent ``masked_account`` or ``account``."""
    base = _transfer_receipt_lines()
    cuenta_idx = next(i for i, line in enumerate(base) if line.startswith("Cuenta ****"))
    parser = ContinentalReceiptParser()
    for line in ("Cuenta 2 5205", "Cuenta 59401", "Cuenta 301112233"):
        lines = list(base)
        lines[cuenta_idx] = line
        receipt = parser.parse_ocr(_ocr(lines), variant=ContinentalVariant.TRANSFER_RECEIPT)
        assert receipt.sender is not None
        assert receipt.sender.account is None
        assert receipt.sender.masked_account is None
