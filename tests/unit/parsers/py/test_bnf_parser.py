"""Synthetic BNF parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.py.bnf import BnfReceiptParser, BnfVariant


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


def _transfer_sent_card_lines() -> list[str]:
    return [
        "Transferencia Enviada",
        "GS, 20.000",
        "sip",
        "Destinatario",
        "CLIENTE EJEMPLO UNO",
        "Cuenta destino",
        "301112233",
        "Entidad destino",
        "SOLAR BANCO S.A.E.",
        "Monto",
        "GS. 20.000",
        "Moneda",
        "GUARANÍES",
        "Cuenta origen",
        "000-99-0888777",
        "Tipo de cuenta",
        "Caja de Ahorro",
        "Fecha y hora",
        "30/09/2026 - 20:47",
        "Nro. de Comprobante",
        "3899901",
    ]


def _operation_success_lines() -> list[str]:
    return [
        "¡Operación Exitosa!",
        "SIP BNF",
        "Fecha de Operación 2026-10-01 15:37:33",
        "Nro. Comprobante: 4107700",
        "Detalle: Transferencia a Cuentas de otros Bancos - SIP",
        "Enviado por: PELOZO EJEMPLO, REMITENTE TRES",
        "Cuenta destino: CLIENTE EJEMPLO UNO",
        "301112233",
        "Banco/Cooperativa: SOLAR BANCO S.A.E.",
        "Monto: Gs 70.000",
        "Concepto: .",
    ]


def test_transfer_sent_card_full() -> None:
    receipt = BnfReceiptParser().parse_ocr(
        _ocr(_transfer_sent_card_lines()),
        variant=BnfVariant.TRANSFER_SENT_CARD,
    )
    assert receipt.issuer == Issuer.BNF
    assert receipt.amount == Decimal("20000")
    assert receipt.currency == "PYG"
    assert receipt.payment_network == "SIP"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-09-30T20:47:00"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status is None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "CLIENTE EJEMPLO UNO"
    assert receipt.recipient.account == "301112233"
    assert receipt.recipient.bank == "SOLAR BANCO S.A.E."
    assert receipt.sender is not None
    assert receipt.sender.name is None
    assert receipt.sender.account == "000-99-0888777"
    assert receipt.sender.bank is None
    assert receipt.sender.account_type == AccountType.SAVINGS
    assert receipt.concept is None
    assert len(receipt.transaction_identifiers) == 1
    assert receipt.transaction_identifiers[0].value == "3899901"
    assert receipt.transaction_identifiers[0].value != receipt.recipient.account


def test_operation_success_receipt_full() -> None:
    receipt = BnfReceiptParser().parse_ocr(
        _ocr(_operation_success_lines()),
        variant=BnfVariant.OPERATION_SUCCESS_RECEIPT,
    )
    assert receipt.amount == Decimal("70000")
    assert receipt.currency == "PYG"
    assert receipt.payment_network == "SIP"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-10-01T15:37:33"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "¡Operación Exitosa!"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "CLIENTE EJEMPLO UNO"
    assert receipt.recipient.account == "301112233"
    assert receipt.recipient.bank == "SOLAR BANCO S.A.E."
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE TRES PELOZO EJEMPLO"
    assert receipt.sender.account is None
    assert receipt.sender.bank is None
    assert receipt.sender.account_type == AccountType.UNKNOWN
    assert receipt.concept is None
    assert receipt.transaction_identifiers[0].value == "4107700"


def test_enviado_por_name_no_reorder_without_single_comma() -> None:
    assert natural_name_from_single_comma("JANE DOE") == "JANE DOE"
    assert natural_name_from_single_comma("A, B, C") == "A, B, C"


def test_concept_dot_becomes_null() -> None:
    receipt = BnfReceiptParser().parse_ocr(
        _ocr(_operation_success_lines()),
        variant=BnfVariant.OPERATION_SUCCESS_RECEIPT,
    )
    assert receipt.concept is None


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError, match="Unsupported BNF"):
        BnfReceiptParser().parse_ocr(_ocr(_transfer_sent_card_lines()), variant="unknown_variant")


def test_minimal_ocr_leaves_fields_null() -> None:
    receipt = BnfReceiptParser().parse_ocr(
        _ocr(["sip", "Monto", "10.000"]),
        variant=BnfVariant.TRANSFER_SENT_CARD,
    )
    assert receipt.issuer == Issuer.BNF
    assert receipt.recipient is None or receipt.recipient.name is None
    assert receipt.sender is None or receipt.sender.bank is None


def test_invalid_date_yields_null_occurred_at() -> None:
    lines = _transfer_sent_card_lines()
    lines[lines.index("30/09/2026 - 20:47")] = "31/02/2026 - 20:47"
    receipt = BnfReceiptParser().parse_ocr(_ocr(lines), variant=BnfVariant.TRANSFER_SENT_CARD)
    assert receipt.occurred_at is None


def test_operation_success_split_title_raw_status() -> None:
    lines = [
        "¡Operación",
        "Exitosa!",
        "Fecha de Operación 2026-10-01 15:37:33",
        "Detalle: otros bancos SIP",
        "Enviado por: PELOZO EJEMPLO, REMITENTE TRES",
        "Monto: Gs 70.000",
    ]
    receipt = BnfReceiptParser().parse_ocr(
        _ocr(lines),
        variant=BnfVariant.OPERATION_SUCCESS_RECEIPT,
    )
    assert receipt.raw_status == "¡Operación Exitosa!"
    assert receipt.status == TransferStatus.COMPLETED
