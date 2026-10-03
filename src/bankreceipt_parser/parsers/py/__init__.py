"""Paraguay (ISO 3166-1 alpha-2: py) bank receipt parsers."""

from bankreceipt_parser.parsers.py.atlas import AtlasReceiptParser
from bankreceipt_parser.parsers.py.bnf import BnfReceiptParser
from bankreceipt_parser.parsers.py.continental import ContinentalReceiptParser
from bankreceipt_parser.parsers.py.familiar import FamiliarReceiptParser
from bankreceipt_parser.parsers.py.gnb import GnbReceiptParser
from bankreceipt_parser.parsers.py.itau import ItauReceiptParser
from bankreceipt_parser.parsers.py.mango import MangoReceiptParser
from bankreceipt_parser.parsers.py.ueno import UenoReceiptParser

__all__ = [
    "AtlasReceiptParser",
    "BnfReceiptParser",
    "ContinentalReceiptParser",
    "FamiliarReceiptParser",
    "GnbReceiptParser",
    "ItauReceiptParser",
    "MangoReceiptParser",
    "UenoReceiptParser",
]
