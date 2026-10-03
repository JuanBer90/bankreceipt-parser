"""BNF (Banco Nacional de Fomento) receipt parser (Paraguay)."""

from bankreceipt_parser.parsers.py.bnf.parser import BnfReceiptParser
from bankreceipt_parser.parsers.py.bnf.variants import BnfVariant

__all__ = ["BnfReceiptParser", "BnfVariant"]
