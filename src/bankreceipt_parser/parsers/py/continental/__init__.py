"""Banco Continental receipt parser (Paraguay)."""

from bankreceipt_parser.parsers.py.continental.parser import ContinentalReceiptParser
from bankreceipt_parser.parsers.py.continental.variants import ContinentalVariant

__all__ = ["ContinentalReceiptParser", "ContinentalVariant"]
