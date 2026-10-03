"""Mango (TU FINANCIERA) wallet transfer receipt profiles."""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.text import TextSignal

MANGO_SIP_DETAIL = IssuerProfile(
    issuer="mango",
    variant="sip_detail",
    establish_issuer=True,
    min_score=2.4,
    signals=(
        TextSignal(
            signal_id="transferencia_sip",
            phrases=("transferencia", "sip"),
            weight=1.0,
            match_all=True,
        ),
        TextSignal(
            signal_id="tu_financiera",
            phrases=("tu", "financiera"),
            weight=0.9,
            match_all=True,
        ),
        TextSignal(
            signal_id="detalle_header",
            phrases=("detalle",),
            weight=0.6,
        ),
        TextSignal(
            signal_id="enviaste_heading",
            phrases=("enviaste",),
            weight=0.6,
        ),
    ),
)

MANGO_TRANSFER_RECEIPT = IssuerProfile(
    issuer="mango",
    variant="transfer_receipt",
    establish_issuer=True,
    min_score=2.2,
    signals=(
        TextSignal(
            signal_id="mango_brand",
            phrases=("mango",),
            weight=0.9,
        ),
        TextSignal(
            signal_id="monto_heading",
            phrases=("monto",),
            weight=0.7,
        ),
        TextSignal(
            signal_id="tu_financiera",
            phrases=("tu", "financiera"),
            weight=0.8,
            match_all=True,
        ),
        TextSignal(
            signal_id="origen_label",
            phrases=("origen",),
            weight=0.5,
        ),
    ),
)

ALL_MANGO_PROFILES: tuple[IssuerProfile, ...] = (
    MANGO_SIP_DETAIL,
    MANGO_TRANSFER_RECEIPT,
)
