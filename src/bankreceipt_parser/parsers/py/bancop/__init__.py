"""BANCOP transfer screen parser."""

from bankreceipt_parser.parsers.py.bancop.parser import BancopReceiptParser
from bankreceipt_parser.parsers.py.bancop.variants import BancopVariant

__all__ = ["BancopReceiptParser", "BancopVariant"]
