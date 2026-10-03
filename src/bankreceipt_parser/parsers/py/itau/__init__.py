"""Itaú Paraguay receipt parser."""

from bankreceipt_parser.parsers.py.itau.parser import ItauReceiptParser
from bankreceipt_parser.parsers.py.itau.variants import ItauVariant

__all__ = ["ItauReceiptParser", "ItauVariant"]
