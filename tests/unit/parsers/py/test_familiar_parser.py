"""Synthetic Banco Familiar parser tests (invented data only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.familiar import FamiliarReceiptParser, FamiliarVariant
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


def _transfer_loaded_lines() -> list[str]:
    return [
        "Transferencia cargada con exito",
        "Monto a enviar",
        "Gs. 88.000",
        "A la cuenta de",
        "RECIPIENTE EJEMPLO UNO",
        "Banco Destino S.A.E. Gs + N°",
        "900011122233",
        "Enviado por",
        "REMITENTE EJEMPLO DOS",
        "Cuenta N°",
        "0-9999****",
        "Fecha Hora",
        "02-Nov-2026 14:05 h",
    ]


def _transfer_confirmed_lines() -> list[str]:
    return [
        "TRANSFERENCIA A OTRAS ENTIDADES CONFIRMADA",
        "Familiar a toda hora",
        "Cliente Pagador: | APELLIDO EJEMPLO, NOMBRE EJEMPLO TRES",
        "Entidad Pagadora: BANCO ORIGEN S.A.E.C.A.",
        "Cliente Beneficiario: | RECIPIENTE EJEMPLO CUATRO",
        "Nro. de Cuenta del 900022233344",
        "Entidad Beneficiaria: BANCO DESTINO S.A.E.",
        "Moneda y Monto: PYG 77.000",
        "Nro. de Operación: 12345678",
        "Referencia: FAMI-TEST-REF",
        "Fecha de Operación: 03/11/2026 09:15:00",
    ]


def test_transfer_loaded_parses_amount_and_sender() -> None:
    receipt = FamiliarReceiptParser().parse_ocr(
        _ocr(_transfer_loaded_lines()),
        variant=FamiliarVariant.TRANSFER_LOADED,
    )
    assert receipt.issuer == Issuer.FAMILIAR
    assert receipt.amount == Decimal("88000")
    assert receipt.currency == "PYG"
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.sender is not None
    assert receipt.sender.name == "REMITENTE EJEMPLO DOS"
    assert receipt.sender.masked_account == "0-9999****"
    assert receipt.recipient is not None
    assert receipt.recipient.name == "RECIPIENTE EJEMPLO UNO"
    assert receipt.recipient.bank == "Banco Destino S.A.E."
    assert receipt.recipient.account == "900011122233"
    assert receipt.occurred_at is not None
    assert receipt.occurred_at.year == 2026


def test_transfer_confirmed_parses_amount_sender_and_identifiers() -> None:
    receipt = FamiliarReceiptParser().parse_ocr(
        _ocr(_transfer_confirmed_lines()),
        variant=FamiliarVariant.TRANSFER_CONFIRMED,
    )
    assert receipt.amount == Decimal("77000")
    assert receipt.sender is not None
    assert receipt.sender.name == "NOMBRE EJEMPLO TRES APELLIDO EJEMPLO"
    assert receipt.sender.bank == "BANCO ORIGEN S.A.E.C.A."
    assert receipt.recipient is not None
    assert receipt.recipient.name == "RECIPIENTE EJEMPLO CUATRO"
    assert receipt.recipient.account == "900022233344"
    assert receipt.recipient.bank == "BANCO DESTINO S.A.E."
    kinds = {item.kind for item in receipt.transaction_identifiers}
    assert TransactionIdentifierKind.OPERATION in kinds
    assert TransactionIdentifierKind.REFERENCE in kinds


def test_registry_exposes_familiar_parser() -> None:
    assert parser_for_issuer(Issuer.FAMILIAR.value) is not None


def test_variant_inference_requires_structure() -> None:
    with pytest.raises(ParseError, match="Could not infer"):
        FamiliarReceiptParser().parse_ocr(_ocr(["Monto a enviar", "Gs. 1.000"]))
