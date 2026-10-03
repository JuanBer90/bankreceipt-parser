"""API coordination tests using synthetic OCR only."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bankreceipt_parser import parse, parse_receipt_text
from bankreceipt_parser.detection.outcome import DetectionStatus, IssuerDetectionOutcome
from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.issuer import Issuer, metadata_for
from bankreceipt_parser.models.party import Party
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.py.bnf import BnfVariant
from bankreceipt_parser.parsers.py.itau import ItauVariant
from bankreceipt_parser.parsers.py.ueno import UenoVariant


def test_api_passes_detected_variant_to_ueno_parser() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.UENO,
        variant=UenoVariant.TRANSFER_SUMMARY,
    )
    receipt = BankTransferReceipt(issuer=Issuer.UENO)
    parser = SimpleNamespace(
        resolve_variant=lambda ocr, variant=None: UenoVariant.TRANSFER_SUMMARY,
        parse_ocr=lambda ocr, country_code=None, variant=None: receipt,
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
    ):
        result = parse_receipt_text("synthetic receipt", include_diagnostics=True)

    assert result.receipt == receipt
    assert result.diagnostics is not None
    assert result.diagnostics.detection.status == DetectionStatus.IDENTIFIED
    assert result.diagnostics.detection.variant == UenoVariant.TRANSFER_SUMMARY
    assert result.diagnostics.parser_variant == UenoVariant.TRANSFER_SUMMARY
    assert not any("parser implementation active" in w for w in result.warnings)


def test_api_canonicalizes_extracted_bank_names_in_public_result() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.UENO,
        variant=UenoVariant.TRANSFER_RECEIPT,
    )
    raw_receipt = BankTransferReceipt(
        issuer=Issuer.UENO,
        sender=Party(bank="UENO S.A. BANK"),
        recipient=Party(bank="bank S.A. ueno"),
    )
    parser = SimpleNamespace(
        resolve_variant=lambda ocr, variant=None: UenoVariant.TRANSFER_RECEIPT,
        parse_ocr=lambda ocr, country_code=None, variant=None: raw_receipt,
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
    ):
        result = parse_receipt_text("synthetic receipt")

    assert result.receipt is not None
    canonical = metadata_for(Issuer.UENO).display_name
    assert result.receipt.sender is not None
    assert result.receipt.sender.bank == canonical
    assert result.receipt.recipient is not None
    assert result.receipt.recipient.bank == canonical


def test_api_passes_detected_variant_to_bnf_parser() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.BNF,
        variant=BnfVariant.TRANSFER_SENT_CARD,
    )
    receipt = BankTransferReceipt(issuer=Issuer.BNF)
    parser = SimpleNamespace(
        resolve_variant=lambda ocr, variant=None: BnfVariant.TRANSFER_SENT_CARD,
        parse_ocr=lambda ocr, country_code=None, variant=None: receipt,
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
    ):
        result = parse_receipt_text("synthetic bnf receipt", include_diagnostics=True)

    assert result.receipt == receipt
    assert result.diagnostics is not None
    assert result.diagnostics.detection.status == DetectionStatus.IDENTIFIED
    assert result.diagnostics.parser_variant == BnfVariant.TRANSFER_SENT_CARD


def test_api_passes_detected_variant_to_itau_parser() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.ITAU,
        variant=ItauVariant.TRANSFER_RECEIPT,
    )
    receipt = BankTransferReceipt(issuer=Issuer.ITAU)
    parser = SimpleNamespace(
        resolve_variant=lambda ocr, variant=None: ItauVariant.TRANSFER_RECEIPT,
        parse_ocr=lambda ocr, country_code=None, variant=None: receipt,
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
    ):
        result = parse_receipt_text("synthetic itau receipt", include_diagnostics=True)

    assert result.receipt == receipt
    assert result.diagnostics is not None
    assert result.diagnostics.detection.status == DetectionStatus.IDENTIFIED
    assert result.diagnostics.parser_variant == ItauVariant.TRANSFER_RECEIPT


def test_api_unknown_detection_skips_parsing() -> None:
    detection = IssuerDetectionOutcome(status=DetectionStatus.UNKNOWN)
    with patch("bankreceipt_parser.api.detect_issuer", return_value=detection):
        result = parse_receipt_text("synthetic unknown", include_diagnostics=True)

    assert result.receipt is None
    assert result.diagnostics is not None
    assert result.diagnostics.detection.status == DetectionStatus.UNKNOWN
    assert any("could not be determined" in w for w in result.warnings)


def test_api_identified_issuer_parse_error_keeps_detection_status() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.ITAU,
        variant=ItauVariant.TRANSFER_RECEIPT,
    )
    ocr_warning = "synthetic OCR language fallback"
    ocr = OCRResult(
        text="synthetic itau receipt",
        elements=[],
        image_width=1,
        image_height=1,
        warnings=(ocr_warning,),
    )

    def _raise_parse_error(*_args: object, **_kwargs: object) -> None:
        raise ParseError("Could not infer Itaú receipt variant from OCR.")

    parser = SimpleNamespace(
        resolve_variant=_raise_parse_error,
        parse_ocr=_raise_parse_error,
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
    ):
        result = parse_receipt_text("synthetic itau receipt", ocr=ocr, include_diagnostics=True)

    assert result.receipt is None
    assert result.diagnostics is not None
    assert result.diagnostics.detection.status == DetectionStatus.IDENTIFIED
    assert result.diagnostics.detection.issuer == Issuer.ITAU
    assert any("receipt parsing failed" in w for w in result.warnings)
    assert not any("parser not implemented" in w for w in result.warnings)


def test_api_parse_error_preserves_ocr_warnings_from_parse() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.BNF,
    )
    ocr_warning = "synthetic OCR tessdata fallback"
    ocr = OCRResult(
        text="synthetic bnf",
        elements=[],
        image_width=1,
        image_height=1,
        warnings=(ocr_warning,),
    )

    def _raise_parse_error(*_args: object, **_kwargs: object) -> None:
        raise ParseError("Could not infer BNF receipt variant from OCR.")

    parser = SimpleNamespace(
        resolve_variant=_raise_parse_error,
        parse_ocr=_raise_parse_error,
    )
    with (
        patch(
            "bankreceipt_parser.api.extract_ocr_with_oriented_image",
            return_value=(ocr, None),
        ),
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
    ):
        result = parse("synthetic.png")

    assert result.receipt is None
    assert ocr_warning in result.warnings
    assert any("receipt parsing failed" in w for w in result.warnings)


def test_api_parser_unexpected_error_propagates() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=Issuer.UENO,
        variant=UenoVariant.TRANSFER_SUMMARY,
    )

    def _raise_type_error(*_args: object, **_kwargs: object) -> None:
        raise TypeError("synthetic parser bug")

    parser = SimpleNamespace(
        resolve_variant=lambda ocr, variant=None: UenoVariant.TRANSFER_SUMMARY,
        parse_ocr=_raise_type_error,
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=parser),
        pytest.raises(TypeError, match="synthetic parser bug"),
    ):
        parse_receipt_text("synthetic receipt")


def test_api_identified_issuer_without_parser_keeps_detection_status() -> None:
    detection = IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer="basa",
    )
    with (
        patch("bankreceipt_parser.api.detect_issuer", return_value=detection),
        patch("bankreceipt_parser.api.parser_for_issuer", return_value=None),
    ):
        result = parse_receipt_text("synthetic basa receipt", include_diagnostics=True)

    assert result.receipt is None
    assert result.diagnostics is not None
    assert result.diagnostics.detection.status == DetectionStatus.IDENTIFIED
    assert result.diagnostics.detection.issuer == "basa"
    assert any("parser not implemented" in w for w in result.warnings)
