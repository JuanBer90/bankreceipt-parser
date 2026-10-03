"""Tests for bank-name normalization."""

from __future__ import annotations

import pytest

from bankreceipt_parser.models.issuer import Issuer, metadata_for
from bankreceipt_parser.models.party import Party
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.normalization import normalize_bank_name
from bankreceipt_parser.normalization.receipt import normalize_receipt_bank_names
from bankreceipt_parser.normalization.registry import CANONICAL_SOLAR_BANCO


@pytest.mark.parametrize(
    "extracted",
    [
        "UENO S.A. BANK",
        "bank S.A. ueno",
        "ueno bank S.A.",
    ],
)
def test_normalize_bank_name_ueno_permutations(extracted: str) -> None:
    assert normalize_bank_name(extracted) == metadata_for(Issuer.UENO).display_name


def test_normalize_bank_name_preserves_unknown_institution() -> None:
    assert normalize_bank_name("FINANCIERA DEMO") == "FINANCIERA DEMO"
    assert normalize_bank_name("BANCO EJEMPLO S.A.") == "BANCO EJEMPLO S.A."


def test_normalize_bank_name_rejects_partial_ueno_token_set() -> None:
    assert normalize_bank_name("ueno bank") == "ueno bank"


@pytest.mark.parametrize(
    "extracted",
    [
        "SOLAR BANCO S.A.E.",
        "SOLAR BANCO S.A.E",
        "SOLAR BANCO SOCIEDAD ANONIMA EMISORA (...",
        "Entidad Destino: SOLAR BANCO (24/7)",
    ],
)
def test_normalize_bank_name_solar_variants(extracted: str) -> None:
    assert normalize_bank_name(extracted) == CANONICAL_SOLAR_BANCO


def test_normalize_bank_name_solar_requires_banco_token() -> None:
    assert normalize_bank_name("SOLAR FINANCIERA S.A.") == "SOLAR FINANCIERA S.A."


def test_normalize_receipt_bank_names_solar_truncated_legal_name() -> None:
    receipt = BankTransferReceipt(
        issuer=Issuer.MEDALLA_MILAGROSA,
        recipient=Party(bank="SOLAR BANCO SOCIEDAD ANONIMA EMISORA (..."),
    )
    normalized = normalize_receipt_bank_names(receipt)
    assert normalized.recipient is not None
    assert normalized.recipient.bank == CANONICAL_SOLAR_BANCO


def test_normalize_receipt_bank_names_updates_parties() -> None:
    receipt = BankTransferReceipt(
        issuer=Issuer.UENO,
        sender=Party(bank="bank S.A. ueno"),
        recipient=Party(bank="BANCO AJENO S.A."),
    )
    normalized = normalize_receipt_bank_names(receipt)
    assert normalized.sender is not None
    assert normalized.sender.bank == "UENO BANK S.A."
    assert normalized.recipient is not None
    assert normalized.recipient.bank == "BANCO AJENO S.A."
