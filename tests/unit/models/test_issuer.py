"""Tests for issuer domain types."""

from __future__ import annotations

from bankreceipt_parser.models.issuer import ISSUER_METADATA, Issuer, metadata_for


def test_every_issuer_has_metadata_display_name() -> None:
    expected = {
        Issuer.UENO: "UENO BANK S.A.",
        Issuer.BNF: "BANCO NACIONAL DE FOMENTO",
        Issuer.ITAU: "BANCO ITAU PARAGUAY S.A.",
        Issuer.GNB: "BANCO GNB PARAGUAY S.A.E.C.A.",
        Issuer.ATLAS: "BANCO ATLAS S.A.",
        Issuer.CONTINENTAL: "BANCO CONTINENTAL S.A.E.C.A.",
        Issuer.COMECIPAR: "COOP COOMECIPAR LTDA",
        Issuer.BANCOP: "BANCOP S.A.",
        Issuer.BASA: "BANCO BASA S.A.E.C.A.",
        Issuer.ECLUB: "eCLUB",
        Issuer.EKO: "EKO",
        Issuer.FAMILIAR: "BANCO FAMILIAR S.A.E.C.A.",
        Issuer.INTERFISA: "INTERFISA BANCO S.A.E.C.A.",
        Issuer.FINANCIERA_PYJ: "FINANCIERA PARAGUAYO JAPONESA S.A.E.C.A.",
        Issuer.MANGO: "MANGO",
        Issuer.MEDALLA_MILAGROSA: "COOPERATIVA MEDALLA MILAGROSA LTDA.",
        Issuer.SUDAMERIS: "SUDAMERIS BANK S.A.E.C.A.",
        Issuer.VAQUITA: "VAQUITA",
        Issuer.ZETA: "ZETA BANCO S.A.E.C.A.",
    }
    assert set(ISSUER_METADATA) == set(Issuer)
    for issuer, display_name in expected.items():
        assert metadata_for(issuer).display_name == display_name
