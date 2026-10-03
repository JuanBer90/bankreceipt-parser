"""Account type helper tests."""

from __future__ import annotations

from bankreceipt_parser.models.enums import AccountType
from bankreceipt_parser.parsers.common.account_type import account_type_from_text


def test_account_type_from_text_caja_de_ahorro() -> None:
    assert account_type_from_text("Caja de Ahorro") == AccountType.SAVINGS


def test_account_type_from_text_ahorros() -> None:
    assert account_type_from_text("ahorros") == AccountType.SAVINGS


def test_account_type_from_text_cuenta_corriente() -> None:
    assert account_type_from_text("Cuenta corriente") == AccountType.CHECKING


def test_account_type_from_text_cc_abbreviation() -> None:
    assert account_type_from_text("cc") == AccountType.CHECKING


def test_account_type_from_text_ah_abbreviation() -> None:
    assert account_type_from_text("AH") == AccountType.SAVINGS


def test_account_type_from_text_unknown() -> None:
    assert account_type_from_text("inversion") == AccountType.UNKNOWN


def test_account_type_from_text_empty() -> None:
    assert account_type_from_text("") == AccountType.UNKNOWN


def test_account_type_from_text_ueno_line_with_account_number() -> None:
    assert account_type_from_text("Caja de ahorro Nro. 100200300") == AccountType.SAVINGS
