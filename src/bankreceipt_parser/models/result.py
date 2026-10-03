"""Parse pipeline result wrapper (receipt + metadata)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from bankreceipt_parser.detection.outcome import IssuerDetectionOutcome
from bankreceipt_parser.models.receipt import BankTransferReceipt


class ParseDiagnostics(BaseModel):
    """Optional end-to-end parsing diagnostics for explicit development use."""

    detection: IssuerDetectionOutcome
    parser_variant: str | None = None


class ParseResult(BaseModel):
    """Outcome of parsing, including non-domain metadata."""

    receipt: BankTransferReceipt | None = None
    raw_ocr_text: str | None = Field(
        default=None,
        exclude=True,
        description="Raw OCR text, included only when explicitly requested for debugging.",
    )
    diagnostics: ParseDiagnostics | None = Field(
        default=None,
        exclude=True,
        description="Optional issuer-detection diagnostics for explicit development use.",
    )
    warnings: list[str] = Field(default_factory=list)
