"""INTERFISA transfer receipt profiles."""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.text import TextSignal

INTERFISA_TRANSFER_LOADED = IssuerProfile(
    issuer="interfisa",
    variant="transfer_loaded",
    establish_issuer=True,
    min_score=2.2,
    signals=(
        TextSignal(
            signal_id="transfer_loaded_header",
            phrases=("transferencia", "cargada"),
            weight=1.0,
            match_all=True,
        ),
        TextSignal(
            signal_id="transaction_number_label",
            phrases=("transaccion",),
            weight=0.7,
        ),
        TextSignal(
            signal_id="debit_account_label",
            phrases=("cuenta", "debit"),
            weight=0.8,
            match_all=True,
        ),
        TextSignal(
            signal_id="beneficiary_document_label",
            phrases=("documento", "benefici"),
            weight=0.7,
            match_all=True,
        ),
    ),
)

ALL_INTERFISA_PROFILES: tuple[IssuerProfile, ...] = (INTERFISA_TRANSFER_LOADED,)
