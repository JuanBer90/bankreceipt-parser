"""Library-specific exceptions."""


class BankReceiptParserError(Exception):
    """Base error for bankreceipt-parser."""


class ImageLoadError(BankReceiptParserError):
    """Image input could not be loaded (missing file, empty data, etc.)."""


class ImageTooLargeError(ImageLoadError):
    """Image dimensions exceed the library's safe processing limit."""


class UnsupportedImageError(BankReceiptParserError):
    """Image format is unsupported or the file is corrupt."""


class OCRError(BankReceiptParserError):
    """OCR processing failed."""


class OCRUnavailableError(OCRError):
    """OCR backend (e.g. Tesseract executable) is not available."""


class OCRProcessingError(OCRError):
    """OCR ran but failed to produce text."""


class QRDecodeError(BankReceiptParserError):
    """QR code decoding failed."""


class IssuerDetectionError(BankReceiptParserError):
    """Could not determine receipt issuer."""


class ParseError(BankReceiptParserError):
    """Receipt text could not be parsed into structured data."""
