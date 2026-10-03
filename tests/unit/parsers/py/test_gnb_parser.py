"""Synthetic GNB parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.gnb import GnbReceiptParser, GnbVariant


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


def _transfer_success_lines() -> list[str]:
    return [
        "GNB",
        "Transferencia Exitosa",
        "Gs. 20.000",
        "Nro. de Operación 77550001",
        "Cuenta debitada 12989000001",
        "Titular TITULAR EJEMPLO CUATRO",
        "Cuenta acreditada 301112233",
        "Beneficiario DESTINATARIO EJEMPLO UNO",
        "Entidad SOLAR BANCO S.A.E",
        "Documento Beneficiario 5551234",
        "Alias 5551234",
        "Concepto Nota ejemplo",
        "Fecha y Hora 30/09/2026 20:13",
        "Importe 20.000",
        "Moneda Guaraníes",
    ]


def _spi_movement_lines() -> list[str]:
    return [
        "Tipo Movimiento",
        "Transferencia enviada SPI",
        "Cuenta",
        "13244000001",
        "Tipo",
        "cc",
        "Monto",
        "Gs. 99.000",
        "Fecha",
        "30/09/2026",
        "Hora",
        "20:31:59",
        "Nombre-Destinatario",
        "DESTINATARIO EJEMPLO UNO",
        "Cuenta-Destinatario",
        "301112233",
        "Documento-Destinatario",
        "CI - 5551234",
        "Banco-Destinatario",
        "SOLAR BANCO S.A.E",
        "Número de comprobante",
        "001000400058199999913420261111",
        "Referencia",
        "BGNBPYPX30099999990064013099",
        "Referencia-Banco",
        "40-581-33999999-20260101",
    ]


def test_transfer_success_parses_core_fields() -> None:
    receipt = GnbReceiptParser().parse_ocr(
        _ocr(_transfer_success_lines()),
        variant=GnbVariant.TRANSFER_SUCCESS,
    )
    assert receipt.issuer == Issuer.GNB
    assert receipt.amount == Decimal("20000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "Transferencia Exitosa"
    assert receipt.payment_network is None
    assert receipt.sender is not None
    assert receipt.sender.account == "12989000001"
    assert receipt.sender.bank is None
    assert receipt.recipient is not None
    assert receipt.recipient.bank == "SOLAR BANCO S.A.E"
    assert receipt.recipient.document_identifier == "5551234"
    assert receipt.recipient.alias == "5551234"
    assert receipt.concept == "Nota ejemplo"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-09-30T20:13:00"


def test_spi_movement_detail_status_and_alias() -> None:
    receipt = GnbReceiptParser().parse_ocr(
        _ocr(_spi_movement_lines()),
        variant=GnbVariant.SPI_MOVEMENT_DETAIL,
    )
    assert receipt.status == TransferStatus.UNKNOWN
    assert receipt.raw_status is None
    assert receipt.payment_network == "SPI"
    assert receipt.recipient is not None
    assert receipt.recipient.document_identifier == "5551234"
    assert receipt.recipient.alias is None
    assert receipt.sender is not None
    assert receipt.sender.account_type == AccountType.CHECKING
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.isoformat() == "2026-09-30T20:31:59"


def test_resolve_variant_from_text() -> None:
    parser = GnbReceiptParser()
    assert (
        parser.resolve_variant(_ocr(_spi_movement_lines()))
        == GnbVariant.SPI_MOVEMENT_DETAIL
    )
    assert parser.resolve_variant(_ocr(_transfer_success_lines())) == GnbVariant.TRANSFER_SUCCESS


def test_unsupported_variant_raises() -> None:
    with pytest.raises(ParseError):
        GnbReceiptParser().parse_ocr(_ocr(_transfer_success_lines()), variant="unknown")
