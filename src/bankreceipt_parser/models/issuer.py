"""Stable issuer identifiers and canonical product metadata.

``Issuer`` values are internal slugs (e.g. JSON ``"issuer": "ueno"``).
``IssuerMetadata.display_name`` is the canonical institution name used by
:func:`bankreceipt_parser.normalization.normalize_bank_name` when an extracted
bank label is recognized. It must not be used to invent ``sender.bank`` or
``recipient.bank`` when the parser did not extract a value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class Issuer(StrEnum):
    """Known receipt issuers (internal stable slug per member)."""

    UENO = "ueno"
    BNF = "bnf"
    ITAU = "itau"
    GNB = "gnb"
    ATLAS = "atlas"
    CONTINENTAL = "continental"
    COMECIPAR = "comecipar"
    BANCOP = "bancop"
    BASA = "basa"
    ECLUB = "eclub"
    EKO = "eko"
    FAMILIAR = "familiar"
    MANGO = "mango"
    INTERFISA = "interfisa"
    FINANCIERA_PYJ = "financiera_pyj"
    MEDALLA_MILAGROSA = "medalla_milagrosa"
    SUDAMERIS = "sudameris"
    VAQUITA = "vaquita"
    ZETA = "zeta"


@dataclass(frozen=True)
class IssuerMetadata:
    """Canonical issuer identity separate from the internal slug."""

    display_name: str  # Canonical bank name for normalization, not OCR auto-fill.


ISSUER_METADATA: Mapping[Issuer, IssuerMetadata] = {
    Issuer.UENO: IssuerMetadata(display_name="UENO BANK S.A."),
    Issuer.BNF: IssuerMetadata(display_name="BANCO NACIONAL DE FOMENTO"),
    Issuer.ITAU: IssuerMetadata(display_name="BANCO ITAU PARAGUAY S.A."),
    Issuer.GNB: IssuerMetadata(display_name="BANCO GNB PARAGUAY S.A.E.C.A."),
    Issuer.ATLAS: IssuerMetadata(display_name="BANCO ATLAS S.A."),
    Issuer.CONTINENTAL: IssuerMetadata(display_name="BANCO CONTINENTAL S.A.E.C.A."),
    Issuer.COMECIPAR: IssuerMetadata(display_name="COOP COOMECIPAR LTDA"),
    Issuer.BANCOP: IssuerMetadata(display_name="BANCOP S.A."),
    Issuer.BASA: IssuerMetadata(display_name="BANCO BASA S.A.E.C.A."),
    Issuer.ECLUB: IssuerMetadata(display_name="eCLUB"),
    Issuer.EKO: IssuerMetadata(display_name="EKO"),
    Issuer.FAMILIAR: IssuerMetadata(display_name="BANCO FAMILIAR S.A.E.C.A."),
    Issuer.INTERFISA: IssuerMetadata(display_name="INTERFISA BANCO S.A.E.C.A."),
    Issuer.FINANCIERA_PYJ: IssuerMetadata(display_name="FINANCIERA PARAGUAYO JAPONESA S.A.E.C.A."),
    Issuer.MANGO: IssuerMetadata(display_name="MANGO"),
    Issuer.MEDALLA_MILAGROSA: IssuerMetadata(display_name="COOPERATIVA MEDALLA MILAGROSA LTDA."),
    Issuer.SUDAMERIS: IssuerMetadata(display_name="SUDAMERIS BANK S.A.E.C.A."),
    Issuer.VAQUITA: IssuerMetadata(display_name="VAQUITA"),
    Issuer.ZETA: IssuerMetadata(display_name="ZETA BANCO S.A.E.C.A."),
}


def metadata_for(issuer: Issuer) -> IssuerMetadata:
    """Return canonical metadata for a known issuer."""
    try:
        return ISSUER_METADATA[issuer]
    except KeyError:
        raise KeyError(f"No metadata registered for issuer {issuer!r}.") from None


def display_name_for_issuer_slug(slug: str) -> str | None:
    """Return canonical display name for a registered issuer slug, or ``None`` if unknown."""
    try:
        issuer = Issuer(slug)
    except ValueError:
        return None
    try:
        return metadata_for(issuer).display_name
    except KeyError:
        return None
