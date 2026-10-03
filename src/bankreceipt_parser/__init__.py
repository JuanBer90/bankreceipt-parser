"""Parse and normalize bank transfer receipts."""

from bankreceipt_parser._version import __version__
from bankreceipt_parser.api import (
    extract_ocr,
    extract_text,
    parse,
    parse_receipt_image,
    parse_receipt_text,
)
from bankreceipt_parser.detection.outcome import DetectionStatus, IssuerDetectionOutcome
from bankreceipt_parser.exceptions import (
    BankReceiptParserError,
    ImageLoadError,
    IssuerDetectionError,
    OCRError,
    OCRProcessingError,
    OCRUnavailableError,
    ParseError,
    UnsupportedImageError,
)
from bankreceipt_parser.models import (
    AccountType,
    BankParty,
    BankTransferReceipt,
    ParseResult,
    Party,
    TransactionIdentifier,
    TransactionIdentifierKind,
    TransferStatus,
)
from bankreceipt_parser.ocr import NotImplementedOCREngine, OCREngine, TesseractOCREngine
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers import GenericReceiptParser, ReceiptParser, StructuredReceiptParser

__all__ = [
    "AccountType",
    "BankParty",
    "BankReceiptParserError",
    "BankTransferReceipt",
    "DetectionStatus",
    "GenericReceiptParser",
    "ImageLoadError",
    "IssuerDetectionError",
    "IssuerDetectionOutcome",
    "NormalizedBoundingBox",
    "NotImplementedOCREngine",
    "OCRResult",
    "OCRTextElement",
    "OCREngine",
    "OCRError",
    "OCRProcessingError",
    "OCRUnavailableError",
    "ParseError",
    "ParseResult",
    "Party",
    "ReceiptParser",
    "StructuredReceiptParser",
    "TesseractOCREngine",
    "TransactionIdentifier",
    "TransactionIdentifierKind",
    "TransferStatus",
    "UnsupportedImageError",
    "__version__",
    "extract_ocr",
    "extract_text",
    "parse",
    "parse_receipt_image",
    "parse_receipt_text",
]
