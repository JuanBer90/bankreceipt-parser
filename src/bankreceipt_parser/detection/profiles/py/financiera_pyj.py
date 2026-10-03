"""FINANCIERA PYJ SIP transfer receipt profile."""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.text import TextSignal

FINANCIERA_PYJ_TRANSFER_RECEIPT = IssuerProfile(
    issuer="financiera_pyj",
    variant="transfer_receipt",
    establish_issuer=True,
    min_score=2.3,
    signals=(
        TextSignal(
            signal_id="pyj_brand",
            phrases=("financiera",),
            weight=0.9,
        ),
        TextSignal(
            signal_id="transfer_receipt_title",
            phrases=("comprobante", "transferencia"),
            weight=0.8,
            match_all=True,
        ),
        TextSignal(
            signal_id="titular_label",
            phrases=("nombre", "titular"),
            weight=0.7,
            match_all=True,
        ),
        TextSignal(
            signal_id="debit_account_label",
            phrases=("cuenta", "debito"),
            weight=0.7,
            match_all=True,
        ),
        TextSignal(
            signal_id="ntr_label",
            phrases=("ntr",),
            weight=0.6,
        ),
    ),
)

ALL_FINANCIERA_PYJ_PROFILES: tuple[IssuerProfile, ...] = (FINANCIERA_PYJ_TRANSFER_RECEIPT,)
