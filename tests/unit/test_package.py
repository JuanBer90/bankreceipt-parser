"""Smoke tests for package bootstrap."""

from __future__ import annotations

import tomllib
from pathlib import Path

import bankreceipt_parser
from bankreceipt_parser import (
    BankTransferReceipt,
    ParseResult,
    TransferStatus,
    parse_receipt_text,
)
from bankreceipt_parser.models.identifier import TransactionIdentifier, TransactionIdentifierKind


def test_version_matches_pyproject() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert bankreceipt_parser.__version__ == pyproject["project"]["version"]


def test_public_import_path() -> None:
    assert "bankreceipt_parser" in bankreceipt_parser.__file__


def test_parse_receipt_text_stub() -> None:
    result = parse_receipt_text("hello")
    assert isinstance(result, ParseResult)
    assert result.raw_ocr_text is None
    assert "raw_ocr_text" not in result.model_dump()
    assert result.warnings


def test_raw_ocr_requires_explicit_opt_in_and_stays_out_of_serialization() -> None:
    result = parse_receipt_text("debug-only text", include_raw_ocr=True)
    assert result.raw_ocr_text == "debug-only text"
    assert "raw_ocr_text" not in result.model_dump()
    assert "debug-only text" not in result.model_dump_json()


def test_receipt_model_skeleton() -> None:
    receipt = BankTransferReceipt(
        issuer="example",
        transaction_identifiers=[
            TransactionIdentifier(kind=TransactionIdentifierKind.REFERENCE, value="ABC123"),
        ],
        status=TransferStatus.UNKNOWN,
    )
    assert receipt.issuer == "example"
