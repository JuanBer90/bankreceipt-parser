"""Contextual primary-amount extraction tests."""

from __future__ import annotations

from decimal import Decimal

from bankreceipt_parser.parsers.common.amounts import extract_gs_amount


def test_extracts_labeled_transfer_amount_before_balance_and_fee() -> None:
    lines = [
        "Saldo: Gs. 5.000.000",
        "Monto: Gs. 250.000",
        "Comisión: Gs. 5.000",
    ]
    assert extract_gs_amount(lines, "\n".join(lines)) == Decimal("250000")


def test_extracts_spaced_currency_and_standalone_receipt_amount() -> None:
    assert extract_gs_amount(["Importe Gs . 250.000"], "") == Decimal("250000")
    assert extract_gs_amount(["250.000", "Gs."], "") == Decimal("250000")
