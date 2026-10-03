"""ZETA Banco receipt parser."""

from bankreceipt_parser.parsers.py.zeta.parser import ZetaReceiptParser
from bankreceipt_parser.parsers.py.zeta.variants import ZetaVariant

__all__ = ["ZetaReceiptParser", "ZetaVariant"]
