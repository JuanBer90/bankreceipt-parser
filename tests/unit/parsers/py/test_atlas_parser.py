"""Synthetic Atlas parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.normalization.receipt import normalize_receipt_bank_names
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.atlas import AtlasReceiptParser, AtlasVariant
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
        elements=[
            _el(line, min(0.95, 0.05 + index * 0.03)) for index, line in enumerate(lines)
        ],
    )


def _sample1_lines() -> list[str]:
    return [
        "SIP / BANCO ATLAS",
        "¡Transferencia enviada!",
        "Información de la transferencia",
        "Nro. de Operación: 2610099888777",
        "Ref. Externa: BNITPYPAARES261009900112200015268999",
        "Remitente: REMITENTE EJEMPLO UNO",
        "Cuenta Origen: CC | 1271001",
        "Destinatario",
        "Beneficiario: DESTINATARIO EJEMPLO UNO",
        "Cuenta Destino: 301112233",
        "Entidad Destino: SOLAR BANCO (24/7)",
        "Monto Débito GS: 20.000",
        "Fecha y Hora de Operación: 01/10/2026 - 13:05 Hs",
    ]


def _sample2_lines() -> list[str]:
    return [
        "Sip E BANCO",
        "SIP | BA ATLAS",
        "¡Transferencia enviada!",
        "Información de latransferencia",
        "Nro. de Operación:.2609000111222",
        "Ref. Externa: BNITPYPAARES260900011122300015176999",
        "Remitente: REMITENTE EJEMPLO DOS",
        "Cuenta Origen: AH | 1322002",
        "Destinatario",
        "Beneficiario: DESTINATARIO EJEMPLO",
        "UNO",
        "Cuenta Destino: 301112233",
        "Entidad Destino: SOLAR BANCO (24/7)",
        "Monto Débito GS: 80.000",
        "Fecha y Hora de Operación: 30/09/2026 - 20:28",
        "Hs",
    ]


def test_parse_sample1_core_fields() -> None:
    receipt = AtlasReceiptParser().parse_ocr(
        _ocr(_sample1_lines()),
        variant=AtlasVariant.TRANSFER_RECEIPT,
    )
    assert receipt.issuer == Issuer.ATLAS
    assert receipt.amount == Decimal("20000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status is None
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-10-01T13:05:00"
    assert receipt.payment_network == "SIP"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO UNO"
    assert receipt.sender.account == "1271001"
    assert receipt.sender.account_type == AccountType.CHECKING
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    assert receipt.recipient.account == "301112233"
    assert receipt.recipient.bank == "SOLAR BANCO (24/7)"
    kinds = {item.kind for item in receipt.transaction_identifiers}
    assert TransactionIdentifierKind.OPERATION in kinds
    assert TransactionIdentifierKind.REFERENCE in kinds
    operation = next(
        i for i in receipt.transaction_identifiers if i.kind == TransactionIdentifierKind.OPERATION
    )
    assert operation.value == "2610099888777"


def test_parse_sample2_core_fields() -> None:
    receipt = AtlasReceiptParser().parse_ocr(
        _ocr(_sample2_lines()),
        variant=AtlasVariant.TRANSFER_RECEIPT,
    )
    assert receipt.amount == Decimal("80000")
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-09-30T20:28:00"
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO DOS"
    assert receipt.sender.account_type == AccountType.SAVINGS
    assert receipt.recipient is not None
    assert receipt.recipient.name == "DESTINATARIO EJEMPLO UNO"
    operation = next(
        i for i in receipt.transaction_identifiers if i.kind == TransactionIdentifierKind.OPERATION
    )
    assert operation.value == "2609000111222"


def test_operation_id_strips_leading_colon_dot() -> None:
    receipt = AtlasReceiptParser().parse_ocr(_ocr(_sample2_lines()))
    operation = next(
        i for i in receipt.transaction_identifiers if i.kind == TransactionIdentifierKind.OPERATION
    )
    assert operation.value == "2609000111222"


def test_registry_parser_for_atlas() -> None:
    assert parser_for_issuer("atlas") is not None


def test_normalize_receipt_bank_names_canonicalizes_solar() -> None:
    from bankreceipt_parser.normalization.registry import CANONICAL_SOLAR_BANCO

    receipt = AtlasReceiptParser().parse_ocr(_ocr(_sample1_lines()))
    normalized = normalize_receipt_bank_names(receipt)
    assert normalized.recipient is not None
    assert normalized.recipient.bank == CANONICAL_SOLAR_BANCO


def test_light_and_dark_same_variant() -> None:
    parser = AtlasReceiptParser()
    v1 = parser.resolve_variant(_ocr(_sample1_lines()), variant=None)
    v2 = parser.resolve_variant(_ocr(_sample2_lines()), variant=None)
    assert v1 == AtlasVariant.TRANSFER_RECEIPT
    assert v2 == AtlasVariant.TRANSFER_RECEIPT
