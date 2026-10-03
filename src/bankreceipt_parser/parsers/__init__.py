"""Country- and bank-specific text parsers."""

from bankreceipt_parser.parsers.base import ReceiptParser, StructuredReceiptParser
from bankreceipt_parser.parsers.generic import GenericReceiptParser

__all__ = ["GenericReceiptParser", "ReceiptParser", "StructuredReceiptParser"]
