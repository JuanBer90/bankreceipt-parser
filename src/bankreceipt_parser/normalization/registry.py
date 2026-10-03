"""Bank-name recognition rules (separate from issuer detection lexicon)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bankreceipt_parser.models.issuer import Issuer

# Counterparty institutions (not receipt issuers); canonical labels for normalization only.
CANONICAL_SOLAR_BANCO = "SOLAR BANCO S.A.E."


@dataclass(frozen=True)
class BankNameRule:
    """Conservative token-set match for a known institution."""

    required_tokens: frozenset[str]
    issuer: Issuer | None = None
    canonical_name: str | None = None
    match_mode: Literal["exact", "superset"] = "exact"

    def __post_init__(self) -> None:
        if self.issuer is None and self.canonical_name is None:
            raise ValueError("BankNameRule requires issuer or canonical_name.")
        if self.issuer is not None and self.canonical_name is not None:
            raise ValueError("BankNameRule cannot set both issuer and canonical_name.")


BANK_NAME_RULES: tuple[BankNameRule, ...] = (
    BankNameRule(
        issuer=Issuer.UENO,
        required_tokens=frozenset({"ueno", "bank", "sa"}),
        match_mode="exact",
    ),
    BankNameRule(
        canonical_name=CANONICAL_SOLAR_BANCO,
        required_tokens=frozenset({"solar", "banco"}),
        match_mode="superset",
    ),
)
