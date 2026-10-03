"""Synthetic UENO parser tests (invented data only)."""

from __future__ import annotations

import pytest

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.ueno import UenoReceiptParser, UenoVariant


def _el(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.8, height=0.03),
        line_index=int(y * 100),
    )


def test_ueno_transfer_comprobante_variant() -> None:
    lines = [
        "ueno bank",
        "Comprobante de transferencia",
        "Nro. de comprobante: 999000111222",
        "15/01/2026 las 10:30 h",
        "25.000",
        "Gs.",
        "Transferencia exitosa",
        "DE",
        "ALICE FICTICIA",
        "Caja de ahorro Nro. 100200300",
        "ueno bank S.A.",
        "PARA",
        "BOB INVENTADO",
        "Nro. 400500600",
        "SOLAR BANCO S.A.E.",
        "Enviada a través del sip Paraguay",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=800,
        image_height=1600,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )
    receipt = UenoReceiptParser().parse_ocr(ocr)
    assert receipt.issuer == Issuer.UENO
    assert receipt.amount is not None
    assert receipt.currency == "PYG"
    assert receipt.occurred_at is not None
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "Transferencia exitosa"
    assert receipt.transaction_identifiers[0].value == "999000111222"
    assert receipt.sender is not None
    assert receipt.sender.name == "ALICE FICTICIA"
    assert receipt.sender.account == "100200300"
    assert receipt.sender.account_type == AccountType.SAVINGS
    assert receipt.sender.bank == "ueno bank S.A."
    assert receipt.recipient is not None
    assert receipt.recipient.name == "BOB INVENTADO"
    assert receipt.recipient.account == "400500600"
    assert receipt.recipient.bank == "SOLAR BANCO S.A.E."
    assert receipt.payment_network == "SIP"


def test_ueno_payment_comprobante_variant() -> None:
    lines = [
        "Comprobante de pago",
        "Nro. de comprobante: 888777666555",
        "20/02/2026 las 11:45 h",
        "10.000",
        "cs.",
        "Transferencia Enviada",
        "PARA",
        "Nombre",
        "CAROL DEMO",
        "Cuenta destino",
        "Nro. 707080809",
        "Cuenta origen",
        "Caja de Ahorros Nro. 606070809",
        "Entidad origen",
        "UENO BANK S.A.",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=900,
        image_height=1800,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )
    receipt = UenoReceiptParser().parse_ocr(ocr, variant=UenoVariant.PAYMENT_RECEIPT)
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status is None
    assert receipt.amount is not None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "CAROL DEMO"
    assert receipt.sender is not None
    assert receipt.sender.account == "606070809"


def test_ueno_payment_receipt_enviada_summary_does_not_set_raw_status() -> None:
    lines = [
        "Comprobante de pago",
        "Nro. de comprobante: 111222333444",
        "10.000",
        "cs.",
        "Transferencia Enviada ALICE DEMO a BOB DEMO",
        "PARA",
        "Nombre",
        "CAROL RECIPIENT",
        "Cuenta destino",
        "Nro. 707080809",
        "Cuenta origen",
        "Caja de Ahorros Nro. 606070809",
        "Entidad origen",
        "UENO BANK S.A.",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=900,
        image_height=1800,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )
    receipt = UenoReceiptParser().parse_ocr(ocr, variant=UenoVariant.PAYMENT_RECEIPT)
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status is None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "CAROL RECIPIENT"


@pytest.mark.parametrize(
    "variant,text",
    [
        (UenoVariant.MOVEMENT_DETAIL, "Monto\nGs. 20.000\nDetalle de movimiento"),
        (UenoVariant.TRANSFER_SUMMARY, "Transferiste Gs. 20.000 a PERSONA DEMO"),
    ],
)
def test_ueno_parser_accepts_detection_variant_ids(variant: UenoVariant, text: str) -> None:
    ocr = OCRResult(text=text, image_width=800, image_height=1600)
    receipt = UenoReceiptParser().parse_ocr(ocr, variant=variant)
    assert receipt.issuer == Issuer.UENO


def test_ueno_extracts_any_explicit_counterparty_bank() -> None:
    lines = [
        "Comprobante de transferencia",
        "DE",
        "ALICE DEMO",
        "Caja de ahorro Nro. 100200300",
        "FINANCIERA DEMO",
        "PARA",
        "BOB DEMO",
        "Nro. 400500600",
        "BANCO EJEMPLO S.A.",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=800,
        image_height=1600,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )

    receipt = UenoReceiptParser().parse_ocr(ocr)

    assert receipt.sender is not None
    assert receipt.sender.bank == "FINANCIERA DEMO"
    assert receipt.recipient is not None
    assert receipt.recipient.bank == "BANCO EJEMPLO S.A."


def test_ueno_leaves_sender_bank_empty_without_explicit_entity() -> None:
    lines = [
        "Comprobante de pago",
        "Cuenta origen",
        "Caja de Ahorros Nro. 606070809",
        "Cuenta destino",
        "Nro. 707080809",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=800,
        image_height=1600,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )

    receipt = UenoReceiptParser().parse_ocr(ocr)

    assert receipt.sender is not None
    assert receipt.sender.bank is None


def test_ueno_entity_value_does_not_consume_following_interface_copy() -> None:
    lines = [
        "Transferiste Gs. 20.000 a PERSONA DEMO",
        "Cuenta destino",
        "Nro. 707080809",
        "Entidad",
        "BANCO EJEMPLO S.A.",
        "Hacer otra transferencia",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=800,
        image_height=1600,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )

    receipt = UenoReceiptParser().parse_ocr(ocr, variant=UenoVariant.TRANSFER_SUMMARY)

    assert receipt.recipient is not None
    assert receipt.recipient.bank == "BANCO EJEMPLO S.A."


def test_ueno_rejects_an_explicitly_unsupported_variant() -> None:
    ocr = OCRResult(text="Comprobante", image_width=1, image_height=1)

    for unsupported_variant in ("unsupported", ""):
        with pytest.raises(ParseError, match="Unsupported UENO receipt variant"):
            UenoReceiptParser().parse_ocr(ocr, variant=unsupported_variant)


def _movement_detail_ocr(lines: list[str]) -> OCRResult:
    return OCRResult(
        text="\n".join(lines),
        image_width=800,
        image_height=1600,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )


def test_movement_detail_recipient_from_enviaste_dinero_a() -> None:
    lines = [
        "Enviaste dinero a Jane Doe",
        "O Enviada",
        "DETALLE DE LA TRANSFERENCIA",
        "Monto",
        "Gs. 10.000",
        "Concepto",
        "Transferencia Enviada a Jane Doe",
        "Cuenta destino",
        "Nro. 301112233",
        "Cuenta origen",
        "Caja de Ahorros Nro. 619000111",
        "Entidad origen",
        "UENO BANK S.A.",
    ]
    receipt = UenoReceiptParser().parse_ocr(
        _movement_detail_ocr(lines),
        variant=UenoVariant.MOVEMENT_DETAIL,
    )
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Jane Doe"


def test_movement_detail_recipient_name_not_polluted_by_next_line_badge() -> None:
    lines = [
        "Enviaste dinero a Jane Doe",
        "O Enviada",
    ]
    receipt = UenoReceiptParser().parse_ocr(
        _movement_detail_ocr(lines),
        variant=UenoVariant.MOVEMENT_DETAIL,
    )
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Jane Doe"


def test_movement_detail_raw_status_ocr_badge_o_enviada() -> None:
    lines = [
        "Enviaste dinero a Jane Doe",
        "O Enviada",
        "DETALLE DE LA TRANSFERENCIA",
    ]
    receipt = UenoReceiptParser().parse_ocr(
        _movement_detail_ocr(lines),
        variant=UenoVariant.MOVEMENT_DETAIL,
    )
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "Enviada"


def test_movement_detail_raw_status_clean_badge_enviada() -> None:
    lines = [
        "Enviaste dinero a Jane Doe",
        "Enviada",
        "DETALLE DE LA TRANSFERENCIA",
    ]
    receipt = UenoReceiptParser().parse_ocr(
        _movement_detail_ocr(lines),
        variant=UenoVariant.MOVEMENT_DETAIL,
    )
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status == "Enviada"


def test_payment_receipt_transferencia_enviada_summary_raw_status_still_null() -> None:
    lines = [
        "Comprobante de pago",
        "Transferencia Enviada a Jane Doe",
        "PARA",
        "Nombre",
        "CAROL RECIPIENT",
        "Cuenta destino",
        "Nro. 707080809",
    ]
    ocr = OCRResult(
        text="\n".join(lines),
        image_width=900,
        image_height=1800,
        elements=[_el(line, 0.05 + index * 0.05) for index, line in enumerate(lines)],
    )
    receipt = UenoReceiptParser().parse_ocr(ocr, variant=UenoVariant.PAYMENT_RECEIPT)
    assert receipt.status == TransferStatus.COMPLETED
    assert receipt.raw_status is None
    assert receipt.recipient is not None
    assert receipt.recipient.name == "CAROL RECIPIENT"


def test_movement_detail_concept_unchanged() -> None:
    lines = [
        "Enviaste dinero a Jane Doe",
        "O Enviada",
        "DETALLE DE LA TRANSFERENCIA",
        "Concepto",
        "Transferencia Enviada a Jane",
        "Doe",
        "Cuenta destino",
        "Nro. 301112233",
    ]
    receipt = UenoReceiptParser().parse_ocr(
        _movement_detail_ocr(lines),
        variant=UenoVariant.MOVEMENT_DETAIL,
    )
    assert receipt.recipient is not None
    assert receipt.recipient.name == "Jane Doe"
    assert receipt.concept == "Transferencia Enviada a Jane Doe"
