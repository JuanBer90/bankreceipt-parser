"""Tests for shared person-name normalization."""

from __future__ import annotations

from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma


def test_natural_name_from_single_comma_continental_samples() -> None:
    assert (
        natural_name_from_single_comma("APELLIDO EJ, PERSONA UNO")
        == "PERSONA UNO APELLIDO EJ"
    )
    assert (
        natural_name_from_single_comma("OVIEDO EJ, CLIENTE DOS")
        == "CLIENTE DOS OVIEDO EJ"
    )


def test_natural_name_from_single_comma_unchanged_without_one_comma() -> None:
    assert natural_name_from_single_comma("JANE DOE") == "JANE DOE"
    assert natural_name_from_single_comma("A, B, C") == "A, B, C"
