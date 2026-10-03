"""Tests for BankTransferReceipt serialization."""

from __future__ import annotations

from bankreceipt_parser.models.issuer import Issuer, metadata_for
from bankreceipt_parser.models.receipt import BankTransferReceipt


def test_issuer_display_name_serialized_for_known_issuers() -> None:
    medalla = BankTransferReceipt(issuer=Issuer.MEDALLA_MILAGROSA)
    payload = medalla.model_dump(mode="json")
    assert payload["issuer"] == "medalla_milagrosa"
    assert payload["issuer_display_name"] == metadata_for(Issuer.MEDALLA_MILAGROSA).display_name

    sudameris = BankTransferReceipt(issuer=Issuer.SUDAMERIS)
    payload = sudameris.model_dump(mode="json")
    assert payload["issuer"] == "sudameris"
    assert payload["issuer_display_name"] == metadata_for(Issuer.SUDAMERIS).display_name


def test_issuer_display_name_absent_for_unknown_slug() -> None:
    receipt = BankTransferReceipt(issuer="not_a_registered_issuer")
    payload = receipt.model_dump(mode="json")
    assert payload["issuer"] == "not_a_registered_issuer"
    assert payload["issuer_display_name"] is None
