"""Bank-specific parser protocol (text in, normalized receipt out)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.ocr.structure import OCRResult


@runtime_checkable
class ReceiptParser(Protocol):
    """Text-first entry; stubs and direct callers."""

    issuer: str

    def parse_text(
        self,
        text: str,
        *,
        qr_data: str | None = None,
        country_code: str | None = None,
    ) -> BankTransferReceipt:
        """Parse normalized fields from raw text."""
        ...


@runtime_checkable
class StructuredReceiptParser(ReceiptParser, Protocol):
    """Parsers in registry; used by parse() after OCR and issuer detection."""

    def resolve_variant(
        self,
        ocr: OCRResult,
        *,
        variant: str | None = None,
    ) -> str:
        """Use detection variant or infer layout from structured OCR."""
        ...

    def parse_ocr(
        self,
        ocr: OCRResult,
        *,
        country_code: str | None = None,
        variant: str | None = None,
    ) -> BankTransferReceipt:
        """Parse normalized fields from structured OCR."""
        ...
