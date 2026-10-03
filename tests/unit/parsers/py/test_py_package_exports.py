"""Public exports from parsers.py package."""

from __future__ import annotations

from bankreceipt_parser.parsers.py import GnbReceiptParser


def test_gnb_receipt_parser_from_py_init_exposes_parse_ocr() -> None:
    assert callable(getattr(GnbReceiptParser(), "parse_ocr", None))
