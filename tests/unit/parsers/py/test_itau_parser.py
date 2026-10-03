"""Synthetic Itaú parser tests (invented data only)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.itau import ItauReceiptParser, ItauVariant


def _el(
    text: str,
    *,
    x: float,
    y: float,
    width: float = 0.08,
    line_index: int = 1,
    word_index: int = 1,
) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=x, y=y, width=width, height=0.02),
        line_index=line_index,
        block_index=1,
        paragraph_index=1,
        word_index=word_index,
        level="word",
    )


def _ocr(lines: list[str], elements: list[OCRTextElement] | None = None) -> OCRResult:
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=elements
        or [
            _el(line, x=0.1, y=0.05 + index * 0.04, line_index=index)
            for index, line in enumerate(lines)
        ],
    )


def _transaction_registered_lines() -> list[str]:
    return [
        "Transacción registrada correctamente.",
        "monto",
        "Gs. 20.000",
        "para",
        "Maria Test User",
        "banco de la cuenta",
        "SOLAR BANCO S.A.E",
        "C.I",
        "1234567",
    ]


def _transfer_detailed_lines() -> list[str]:
    return [
        "comprobante de transferencia",
        "monto débito",
        "Gs. 35.000",
        "situación de la transacción",
        "transferencia enviada procesada",
        "de",
        "Sender Person",
        "cuenta en guaraníes",
        "n° 400011122",
        "Destinatario ApellidoGlue Nombre",
        "SOLAR BANCO S.A.E",
        "cuenta en guaraníes",
        "n° 301112233",
        "n° de comprobante",
        "4419001",
        "n° de operación",
        "UBBRPYPXARES260900011122200003409999",
        "fecha y hora de recepción",
        "30/09/2026 00:00 hs.",
        "fecha de movimiento",
        "30/09/2026",
    ]


def test_transaction_registered_complete() -> None:
    receipt = ItauReceiptParser().parse_ocr(
        _ocr(_transaction_registered_lines()),
        variant=ItauVariant.TRANSACTION_REGISTERED,
    )
    assert receipt.issuer == Issuer.ITAU
    assert receipt.amount == Decimal("20000")
    assert receipt.currency == "PYG"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Maria Test User"
    assert receipt.recipient.bank == "SOLAR BANCO S.A.E"
    assert receipt.recipient.document_identifier == "1234567"
    assert receipt.status == TransferStatus.PENDING
    assert receipt.raw_status == "Transacción registrada correctamente."
    assert receipt.occurred_at is None
    assert receipt.sender is None
    assert receipt.payment_network is None


def test_transfer_receipt_detailed_occurred_at_midnight() -> None:
    receipt = ItauReceiptParser().parse_ocr(
        _ocr(_transfer_detailed_lines()),
        variant=ItauVariant.TRANSFER_RECEIPT,
    )
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "transferencia enviada procesada"
    assert receipt.occurred_at == datetime(2026, 9, 30, 0, 0, 0)
    assert receipt.sender is not None
    assert receipt.sender.name == "Sender Person"
    assert receipt.sender.account == "400011122"
    assert receipt.sender.bank is None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Destinatario ApellidoGlue Nombre"
    assert receipt.recipient.account == "301112233"
    assert len(receipt.transaction_identifiers) == 2
    kinds = {item.kind for item in receipt.transaction_identifiers}
    assert TransactionIdentifierKind.TICKET in kinds
    assert TransactionIdentifierKind.OPERATION in kinds


def test_compact_qr_layout_recipient_without_noise() -> None:
    lines = [
        "comprobante de transferencia",
        "Gs. 99.000",
        "para NoiseQR",
        "Persona Prueba @@@@",
        "Apellido Ejemplo http://evil",
        "cuenta en guaranies",
        "n° 301112233",
        "realizada el 01 oct 2026 a las 09:53 hs",
    ]
    elements: list[OCRTextElement] = []
    for line_index, line in enumerate(lines):
        y = 0.05 + line_index * 0.04
        x = 0.10
        for word_index, token in enumerate(line.split(), start=1):
            width = max(0.05, len(token) * 0.012)
            if line_index == 2 and token != "para":
                x = 0.62
            if line_index in {3, 4} and token in {"@@@@", "http://evil"}:
                x = 0.65
            elements.append(
                _el(
                    token,
                    x=x,
                    y=y,
                    width=width,
                    line_index=line_index,
                    word_index=word_index,
                )
            )
            x += width + 0.02
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=elements,
    )
    receipt = ItauReceiptParser().parse_ocr(ocr, variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Persona Prueba Apellido Ejemplo"
    assert "@" not in (receipt.recipient.name or "")
    assert "http" not in (receipt.recipient.name or "")
    assert receipt.recipient.account == "301112233"


def test_itau2_alias_and_realizada_date() -> None:
    lines = [
        "comprobante de transferencia",
        "Gs. 25.000",
        "de",
        "REMITENTE PRUEBA EJEMPLO",
        "cuenta débito n° 320500111",
        "para",
        "Persona PruebasApellido Ejemplo",
        "Alias",
        "5551234",
        "numero de comprobante",
        "1888777",
        "realizada el 01 oct 2026 a las 13:32 hs",
    ]
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.sender is not None
    assert receipt.sender.account == "320500111"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Persona PruebasApellido Ejemplo"
    assert receipt.recipient.alias == "5551234"
    assert receipt.recipient.account is None
    assert receipt.occurred_at == datetime(2026, 10, 1, 13, 32, 0)
    assert receipt.transaction_identifiers[0].value == "1888777"


def test_debit_account_not_gt_para_line_r1() -> None:
    lines = [
        "comprobante de transferencia",
        "Gs. 25.000",
        "de",
        "REMITENTE PRUEBA EJEMPLO",
        "cuenta débito n° 320500111",
        "GT para",
        "Persona PruebasApellido Ejemplo",
        "Alias",
        "5551234",
    ]
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.sender is not None
    assert receipt.sender.account == "320500111"
    assert receipt.sender.account != "GT para"


def test_recipient_name_from_para_layout_r2() -> None:
    lines = [
        "comprobante de transferencia",
        "Gs. 25.000",
        "de",
        "REMITENTE PRUEBA EJEMPLO",
        "cuenta débito n° 320500111",
        "GT para",
        "ve",
        '"> Persona PruebasApellido Ejemplo',
        "Alias fa",
        "5551234",
        "numero de comprobante",
        "1888777",
        "realizada el 01 oct 2026 a las 13:32 hs",
    ]
    y_para = 0.51
    elements: list[OCRTextElement] = [
        _el("comprobante", x=0.10, y=0.20, width=0.12, line_index=0, word_index=1),
        _el("de", x=0.24, y=0.20, width=0.03, line_index=0, word_index=2),
        _el("transferencia", x=0.28, y=0.20, width=0.12, line_index=0, word_index=3),
        _el("cuenta", x=0.19, y=0.46, width=0.08, line_index=5, word_index=1),
        _el("débito", x=0.28, y=0.46, width=0.06, line_index=5, word_index=2),
        _el("n°", x=0.38, y=0.46, width=0.03, line_index=5, word_index=3),
        _el("320500111", x=0.42, y=0.46, width=0.12, line_index=5, word_index=4),
        _el("GT", x=0.12, y=y_para, width=0.04, line_index=6, word_index=1),
        _el("para", x=0.19, y=y_para, width=0.05, line_index=6, word_index=2),
        _el("ve", x=0.10, y=0.55, width=0.03, line_index=7, word_index=1),
        _el('">', x=0.14, y=0.55, width=0.03, line_index=7, word_index=2),
        _el("Persona", x=0.19, y=0.55, width=0.10, line_index=7, word_index=3),
        _el("PruebasApellido", x=0.32, y=0.55, width=0.14, line_index=7, word_index=4),
        _el("Ejemplo", x=0.48, y=0.55, width=0.06, line_index=7, word_index=5),
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=elements,
    )
    receipt = ItauReceiptParser().parse_ocr(ocr, variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Persona PruebasApellido Ejemplo"
    assert "ve" not in (receipt.recipient.name or "")
    assert '">' not in (receipt.recipient.name or "")


def test_rejects_invalid_explicit_variant() -> None:
    with pytest.raises(ParseError, match="Unsupported"):
        ItauReceiptParser().parse_ocr(_ocr(_transaction_registered_lines()), variant="unknown")


def test_detect_variant_inference() -> None:
    parser = ItauReceiptParser()
    reg = parser.resolve_variant(_ocr(_transaction_registered_lines()))
    assert reg == ItauVariant.TRANSACTION_REGISTERED
    tr = parser.resolve_variant(_ocr(_transfer_detailed_lines()))
    assert tr == ItauVariant.TRANSFER_RECEIPT


def test_detect_variant_ambiguous_raises() -> None:
    with pytest.raises(ParseError):
        ItauReceiptParser().resolve_variant(_ocr(["hola", "mundo"]))


def test_sender_bank_stays_null() -> None:
    receipt = ItauReceiptParser().parse_ocr(
        _ocr(_transfer_detailed_lines()),
        variant=ItauVariant.TRANSFER_RECEIPT,
    )
    assert receipt.sender is not None
    assert receipt.sender.bank is None


def test_account_type_unknown() -> None:
    receipt = ItauReceiptParser().parse_ocr(
        _ocr(_transfer_detailed_lines()),
        variant=ItauVariant.TRANSFER_RECEIPT,
    )
    assert receipt.recipient is not None
    assert receipt.recipient.account_type == AccountType.UNKNOWN


def test_status_bar_time_ignored_for_occurred_at() -> None:
    base = _transaction_registered_lines()
    lines = base[:2] + ["8:33", "Gs. 20.000"] + base[3:]
    receipt = ItauReceiptParser().parse_ocr(
        _ocr(lines),
        variant=ItauVariant.TRANSACTION_REGISTERED,
    )
    assert receipt.occurred_at is None


def test_invalid_dates_return_none() -> None:
    lines = _transfer_detailed_lines()
    lines[18] = "31/02/2026 00:00 hs."
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.occurred_at is None


def _detailed_block_lines(
    *,
    recipient_lines: list[str],
    recipient_account: str = "987654321",
) -> list[str]:
    return [
        "comprobante de transferencia",
        "monto débito",
        "Gs. 35.000",
        "de",
        "Sender Person",
        "cuenta en guaraníes",
        "n° 400011122",
        *recipient_lines,
        "cuenta en guaraníes",
        f"n° {recipient_account}",
        "n° de comprobante",
        "9999999",
    ]


def test_detailed_recipient_fictional_bank_not_solar() -> None:
    lines = _detailed_block_lines(
        recipient_lines=[
            "Maria Ejemplo Lopez",
            "COOPERATIVA EJEMPLO LTDA.",
        ],
    )
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Maria Ejemplo Lopez"
    assert receipt.recipient.bank == "COOPERATIVA EJEMPLO LTDA."
    assert receipt.recipient.account == "987654321"


def test_detailed_recipient_without_bank_line() -> None:
    lines = _detailed_block_lines(recipient_lines=["Maria Ejemplo Lopez"])
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Maria Ejemplo Lopez"
    assert receipt.recipient.bank is None
    assert receipt.recipient.account == "987654321"


def test_detailed_recipient_multiline_name_and_fictional_bank() -> None:
    lines = _detailed_block_lines(
        recipient_lines=[
            "Maria",
            "Fernanda Ejemplo",
            "COOPERATIVA XYZ LTDA.",
        ],
    )
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Maria Fernanda Ejemplo"
    assert receipt.recipient.bank == "COOPERATIVA XYZ LTDA."


def test_transfer_status_unknown_when_not_processed() -> None:
    lines = _transfer_detailed_lines()
    lines[4] = "en revisión"
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    assert receipt.status == TransferStatus.UNKNOWN
    assert receipt.raw_status == "en revisión"


def test_operation_id_inline_on_same_line() -> None:
    lines = _transfer_detailed_lines()
    lines[16] = "n° de operación ABCDEF123456789"
    lines[17] = ""
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    operation = next(
        item
        for item in receipt.transaction_identifiers
        if item.kind == TransactionIdentifierKind.OPERATION
    )
    assert operation.value == "ABCDEF123456789"


def test_operation_id_does_not_capture_fecha_label() -> None:
    lines = _transfer_detailed_lines()
    lines[15] = "n° de operación"
    lines[16] = "fecha y hora de recepción"
    lines[17] = "30/09/2026 10:30 hs."
    receipt = ItauReceiptParser().parse_ocr(_ocr(lines), variant=ItauVariant.TRANSFER_RECEIPT)
    kinds = {item.kind for item in receipt.transaction_identifiers}
    assert TransactionIdentifierKind.OPERATION not in kinds
