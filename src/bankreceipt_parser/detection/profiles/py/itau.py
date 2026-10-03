"""
ITAU issuer profiles.

Visual issuer evidence measured from private samples: left-clustered orange brand
block (~255,98,0) in the upper-left header. OCR rarely reads the ITAU wordmark.

One sample lacks sufficient orange coverage; it is covered by a unique generic UI
phrase (``transaccion registrada``) present in 1/35 private receipts only.
"""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.layout import NormalizedRegion
from bankreceipt_parser.detection.signals.text import TextAbsenceSignal, TextSignal
from bankreceipt_parser.detection.signals.visual import BrandBlockSignal, BrandDensitySignal

_ITAU_HEADER_LEFT = NormalizedRegion(x=0.0, y=0.0, width=0.55, height=0.28)
_FULL_PAGE = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=1.0)

ITAU_VISUAL_ISSUER = IssuerProfile(
    issuer="itau",
    variant="visual_brand",
    min_score=1.0,
    establish_issuer=True,
    issuer_only=True,
    signals=(
        BrandBlockSignal(
            signal_id="header_orange_logo_block",
            region=_ITAU_HEADER_LEFT,
            target_rgb=(255, 98, 0),
            tolerance=40.0,
            min_left_coverage=0.10,
            min_left_bias=0.55,
            max_median_blue=15.0,
            min_median_red=248.0,
            weight=1.0,
        ),
        BrandDensitySignal(
            signal_id="header_orange_density",
            region=_ITAU_HEADER_LEFT,
            target_rgb=(255, 98, 0),
            tolerance=40.0,
            min_coverage=0.33,
            min_median_red=254.0,
            max_median_blue=15.0,
            weight=1.0,
        ),
    ),
)

ITAU_TEXT_ISSUER = IssuerProfile(
    issuer="itau",
    variant="registered_phrase",
    min_score=1.0,
    establish_issuer=True,
    issuer_only=True,
    signals=(
        TextSignal(
            signal_id="transaccion_registrada",
            phrases=("transaccion registrada",),
            weight=1.0,
        ),
    ),
)

ITAU_TRANSFER_RECEIPT = IssuerProfile(
    issuer="itau",
    variant="transfer_receipt",
    min_score=0.9,
    establish_issuer=False,
    signals=(
        TextSignal(
            signal_id="comprobante_de_transferencia",
            phrases=("comprobante de transferencia",),
            weight=1.0,
        ),
        TextSignal(
            signal_id="comprobante_y_transferencia",
            phrases=("comprobante", "transferencia"),
            weight=0.9,
            match_all=True,
        ),
    ),
    exclusions=(
        TextAbsenceSignal(
            signal_id="no_transaccion_registrada",
            phrases=("transaccion registrada",),
            region=_FULL_PAGE,
        ),
    ),
)

ITAU_TRANSACTION_REGISTERED = IssuerProfile(
    issuer="itau",
    variant="transaction_registered",
    min_score=1.0,
    establish_issuer=False,
    signals=(
        TextSignal(
            signal_id="transaccion_registrada",
            phrases=("transaccion registrada",),
            weight=1.0,
        ),
    ),
)

ALL_ITAU_PROFILES: tuple[IssuerProfile, ...] = (
    ITAU_VISUAL_ISSUER,
    ITAU_TEXT_ISSUER,
    ITAU_TRANSFER_RECEIPT,
    ITAU_TRANSACTION_REGISTERED,
)
