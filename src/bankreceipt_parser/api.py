"""High-level entry points for receipt parsing and OCR."""

from __future__ import annotations

from bankreceipt_parser.detection.issuer import detect_issuer
from bankreceipt_parser.detection.outcome import DetectionStatus, IssuerDetectionOutcome
from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.models.result import ParseDiagnostics, ParseResult
from bankreceipt_parser.normalization import normalize_receipt_bank_names
from bankreceipt_parser.ocr.engine import OCREngine
from bankreceipt_parser.ocr.images import ImageSource
from bankreceipt_parser.ocr.pipeline import (
    extract_ocr_with_details,
    extract_ocr_with_oriented_image,
    extract_text_with_details,
)
from bankreceipt_parser.ocr.preprocessing import PreprocessOptions
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.registry import parser_for_issuer


def _diagnostics(
    detection: IssuerDetectionOutcome,
    *,
    parser_variant: str | None = None,
    include: bool,
) -> ParseDiagnostics | None:
    if not include:
        return None
    return ParseDiagnostics(detection=detection, parser_variant=parser_variant)


def _structured_ocr_parser(parser: object) -> bool:
    return callable(getattr(parser, "parse_ocr", None)) and callable(
        getattr(parser, "resolve_variant", None)
    )


def _parse_with_registry(
    ocr: OCRResult,
    detection: IssuerDetectionOutcome,
    *,
    country_code: str | None = None,
) -> tuple[BankTransferReceipt, str]:
    parser = parser_for_issuer(detection.issuer)
    if parser is None or not _structured_ocr_parser(parser):
        raise ValueError("parser_unavailable")
    parser_variant = parser.resolve_variant(ocr, variant=detection.variant)
    if country_code is not None:
        receipt = parser.parse_ocr(ocr, country_code=country_code, variant=parser_variant)
    else:
        receipt = parser.parse_ocr(ocr, variant=parser_variant)
    return receipt, parser_variant


def extract_text(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
) -> str:
    """
    Extract normalized text from a receipt image using local OCR.

    Supports PNG, JPEG, and WEBP inputs as a file path or raw bytes.
    """
    return extract_text_with_details(
        source,
        ocr_engine=ocr_engine,
        preprocess_options=preprocess_options,
    ).text


def extract_ocr(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
) -> OCRResult:
    """Extract structured OCR (text, elements, normalized bounding boxes)."""
    return extract_ocr_with_details(
        source,
        ocr_engine=ocr_engine,
        preprocess_options=preprocess_options,
    )


def parse(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
    include_raw_ocr: bool = False,
    include_diagnostics: bool = False,
) -> ParseResult:
    """
    OCR + issuer detection + bank-specific parsing when supported.

    Parsed party bank names are canonicalized in this entry point (not in bank parsers).
    """
    ocr, oriented_image = extract_ocr_with_oriented_image(
        source,
        ocr_engine=ocr_engine,
        preprocess_options=preprocess_options,
    )
    warnings = list(ocr.warnings)
    detection = detect_issuer(text=ocr.text, ocr=ocr, image=oriented_image)

    if detection.status == DetectionStatus.UNKNOWN:
        warnings.append("Issuer/format could not be determined; receipt parsing skipped.")
        return ParseResult(
            raw_ocr_text=ocr.text if include_raw_ocr else None,
            diagnostics=_diagnostics(detection, include=include_diagnostics),
            warnings=warnings,
        )

    try:
        receipt, parser_variant = _parse_with_registry(ocr, detection)
    except ValueError:
        warnings.append(
            f"Issuer/format identified as {detection.issuer!r}; parser not implemented yet."
        )
        return ParseResult(
            raw_ocr_text=ocr.text if include_raw_ocr else None,
            diagnostics=_diagnostics(detection, include=include_diagnostics),
            warnings=warnings,
        )
    except ParseError as exc:
        warnings.append(
            f"Issuer/format identified as {detection.issuer!r}; receipt parsing failed: {exc}"
        )
        return ParseResult(
            raw_ocr_text=ocr.text if include_raw_ocr else None,
            diagnostics=_diagnostics(detection, include=include_diagnostics),
            warnings=warnings,
        )

    receipt = normalize_receipt_bank_names(receipt)
    return ParseResult(
        receipt=receipt,
        raw_ocr_text=ocr.text if include_raw_ocr else None,
        diagnostics=_diagnostics(
            detection,
            parser_variant=parser_variant,
            include=include_diagnostics,
        ),
        warnings=warnings,
    )


def parse_receipt_image(
    source: ImageSource,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
    include_raw_ocr: bool = False,
    include_diagnostics: bool = False,
) -> ParseResult:
    """Backward-compatible alias for :func:`parse`."""
    return parse(
        source,
        ocr_engine=ocr_engine,
        preprocess_options=preprocess_options,
        include_raw_ocr=include_raw_ocr,
        include_diagnostics=include_diagnostics,
    )


def parse_receipt_text(
    text: str,
    *,
    country_code: str | None = None,
    ocr: OCRResult | None = None,
    include_raw_ocr: bool = False,
    include_diagnostics: bool = False,
) -> ParseResult:
    """
    Parse already-extracted text (and optional structured OCR) without running OCR.

    Parsed party bank names are canonicalized in this entry point (not in bank parsers).
    """
    detection = detect_issuer(text=text, ocr=ocr)
    warnings: list[str] = []
    if detection.status == DetectionStatus.UNKNOWN:
        warnings.append("Issuer/format could not be determined; receipt parsing skipped.")
        return ParseResult(
            raw_ocr_text=text if include_raw_ocr else None,
            diagnostics=_diagnostics(detection, include=include_diagnostics),
            warnings=warnings,
        )

    structured = ocr or OCRResult(text=text, elements=[], image_width=1, image_height=1)
    try:
        receipt, parser_variant = _parse_with_registry(
            structured,
            detection,
            country_code=country_code,
        )
    except ValueError:
        warnings.append(
            f"Issuer/format identified as {detection.issuer!r}; parser not implemented yet."
        )
        return ParseResult(
            raw_ocr_text=text if include_raw_ocr else None,
            diagnostics=_diagnostics(detection, include=include_diagnostics),
            warnings=warnings,
        )
    except ParseError as exc:
        warnings.append(
            f"Issuer/format identified as {detection.issuer!r}; receipt parsing failed: {exc}"
        )
        return ParseResult(
            raw_ocr_text=text if include_raw_ocr else None,
            diagnostics=_diagnostics(detection, include=include_diagnostics),
            warnings=warnings,
        )

    receipt = normalize_receipt_bank_names(receipt)
    return ParseResult(
        receipt=receipt,
        raw_ocr_text=text if include_raw_ocr else None,
        diagnostics=_diagnostics(
            detection,
            parser_variant=parser_variant,
            include=include_diagnostics,
        ),
        warnings=warnings,
    )
