"""
BASA issuer profile (transfer success screen).

Evidence measured from one independent clean screenshot (duplicate folder file is a
different capture with system chrome; same UI hypothesis, not used for tuning).

Does not treat in-receipt destination bank names as issuer evidence.
"""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.layout import NormalizedRegion
from bankreceipt_parser.detection.signals.order import VerticalOrderSignal
from bankreceipt_parser.detection.signals.text import TextSignal

# Header blue band (median ~0,80,180 on reference layout).
_BASA_BLUE_HEADER = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.22)
_SUCCESS_TITLE = NormalizedRegion(x=0.0, y=0.15, width=1.0, height=0.15)
_ACTION_FOOTER = NormalizedRegion(x=0.0, y=0.78, width=1.0, height=0.22)

BASA_TRANSFER_SUCCESS = IssuerProfile(
    issuer="basa",
    variant="transfer_success",
    min_score=3.2,
    establish_issuer=True,
    signals=(
        ColorRegionSignal(
            signal_id="blue_header_band",
            region=_BASA_BLUE_HEADER,
            target_rgb=(0, 80, 180),
            tolerance=65.0,
            min_coverage=0.85,
            weight=1.2,
        ),
        TextSignal(
            signal_id="transferencia_exitosa_title",
            phrases=("transferencia exitosa",),
            weight=1.0,
            region=_SUCCESS_TITLE,
        ),
        VerticalOrderSignal(
            signal_id="monto_before_fecha",
            upper_phrases=("monto",),
            lower_phrases=("fecha",),
            weight=0.8,
        ),
        TextSignal(
            signal_id="compartir_comprobante_action",
            phrases=("compartir", "comprobante"),
            weight=0.8,
            region=_ACTION_FOOTER,
            match_all=True,
        ),
    ),
)

BASA_PARTY_CARDS = IssuerProfile(
    issuer="basa",
    variant="party_cards",
    min_score=2.6,
    establish_issuer=True,
    signals=(
        TextSignal(
            signal_id="transferencia_exitosa_body",
            phrases=("transferencia", "exitosa"),
            weight=0.9,
            match_all=True,
        ),
        TextSignal(
            signal_id="banco_basa_sender_line",
            phrases=("banco basa",),
            weight=1.0,
        ),
        TextSignal(
            signal_id="comprobante_label",
            phrases=("comprobante",),
            weight=0.7,
        ),
        TextSignal(
            signal_id="realizado_el_stamp",
            phrases=("realizado el",),
            weight=0.7,
        ),
    ),
)

ALL_BASA_PROFILES: tuple[IssuerProfile, ...] = (
    BASA_TRANSFER_SUCCESS,
    BASA_PARTY_CARDS,
)
