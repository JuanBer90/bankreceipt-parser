"""
UENO issuer profiles.

Measurements for ``transfer_summary`` come from programmatic analysis of a private
transfer-summary screenshot (mint header band, upper ``Transferiste`` label, mid
``Detalle`` + ``transferencia``, destination field labels). Values use normalized
layout and RGB tolerance — not filename or pixel dimensions.
"""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.layout import NormalizedRegion
from bankreceipt_parser.detection.signals.text import TextAbsenceSignal, TextSignal
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.parsers.py.ueno import UenoVariant

# Upper mint header band (median RGB ~122,245,191 on reference receipt).
_UENO_MINT_HEADER = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.35)

# Text bands derived from normalized OCR element centers on reference layout.
_UPPER_TRANSFER_LABEL = NormalizedRegion(x=0.0, y=0.12, width=1.0, height=0.22)
_DETAIL_SECTION = NormalizedRegion(x=0.0, y=0.28, width=1.0, height=0.20)
_DESTINATION_FIELDS = NormalizedRegion(x=0.0, y=0.40, width=1.0, height=0.25)
_ENTITY_LABEL = NormalizedRegion(x=0.0, y=0.48, width=1.0, height=0.22)
_UPPER_DOCUMENT = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.55)

UENO_TRANSFER_SUMMARY = IssuerProfile(
    issuer=Issuer.UENO,
    variant=UenoVariant.TRANSFER_SUMMARY.value,
    min_score=3.4,
    signals=(
        TextSignal(
            signal_id="transferiste_upper",
            phrases=("transferiste",),
            weight=1.0,
            region=_UPPER_TRANSFER_LABEL,
        ),
        TextSignal(
            signal_id="detalle_transferencia",
            phrases=("detalle", "transferencia"),
            weight=1.0,
            region=_DETAIL_SECTION,
            match_all=True,
        ),
        TextSignal(
            signal_id="cuenta_destino",
            phrases=("cuenta", "destino"),
            weight=0.8,
            region=_DESTINATION_FIELDS,
            match_all=True,
        ),
        TextSignal(
            signal_id="entidad_label",
            phrases=("entidad",),
            weight=0.5,
            region=_ENTITY_LABEL,
        ),
        ColorRegionSignal(
            signal_id="mint_header_band",
            region=_UENO_MINT_HEADER,
            target_rgb=(122, 245, 191),
            tolerance=55.0,
            min_coverage=0.5,
            weight=1.2,
        ),
    ),
    exclusions=(
        TextAbsenceSignal(
            signal_id="no_comprobante_transferencia_upper",
            phrases=("comprobante de transferencia",),
            region=_UPPER_DOCUMENT,
        ),
    ),
)

_UPPER_ACTION = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.40)

UENO_PAYMENT_RECEIPT = IssuerProfile(
    issuer=Issuer.UENO,
    variant=UenoVariant.PAYMENT_RECEIPT.value,
    min_score=3.1,
    establish_issuer=False,
    signals=(
        TextSignal(
            signal_id="comprobante_de_pago",
            phrases=("comprobante de pago",),
            weight=1.0,
        ),
        TextSignal(
            signal_id="nro_comprobante",
            phrases=("nro. de comprobante", "nro de comprobante"),
            weight=0.9,
        ),
        TextSignal(
            signal_id="cuenta_destino",
            phrases=("cuenta", "destino"),
            weight=0.7,
            match_all=True,
        ),
        TextSignal(
            signal_id="cuenta_origen",
            phrases=("cuenta", "origen"),
            weight=0.7,
            match_all=True,
        ),
        TextSignal(
            signal_id="entidad_origen",
            phrases=("entidad", "origen"),
            weight=0.7,
            match_all=True,
        ),
    ),
    exclusions=(
        TextAbsenceSignal(
            signal_id="no_transferiste_upper",
            phrases=("transferiste",),
            region=_UPPER_ACTION,
        ),
        TextAbsenceSignal(
            signal_id="no_movimiento_detail",
            phrases=("detalle de movimiento",),
            region=NormalizedRegion(x=0.0, y=0.0, width=1.0, height=1.0),
        ),
    ),
)

_FULL_PAGE = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=1.0)

UENO_MOVEMENT_DETAIL = IssuerProfile(
    issuer=Issuer.UENO,
    variant=UenoVariant.MOVEMENT_DETAIL.value,
    min_score=2.8,
    establish_issuer=False,
    signals=(
        TextSignal(
            signal_id="detalle_movimiento",
            phrases=("detalle de movimiento",),
            weight=1.2,
        ),
        TextSignal(
            signal_id="detalle_de_la_transferencia",
            phrases=("detalle de la transferencia",),
            weight=1.0,
        ),
        TextSignal(
            signal_id="transferencia_enviada",
            phrases=("enviada",),
            weight=0.5,
        ),
        TextSignal(
            signal_id="monto_y_concepto",
            phrases=("monto", "concepto"),
            weight=0.6,
            match_all=True,
        ),
        TextSignal(
            signal_id="entidad_origen",
            phrases=("entidad", "origen"),
            weight=0.5,
            match_all=True,
        ),
        TextSignal(
            signal_id="nro_comprobante",
            phrases=("nro. de comprobante", "nro de comprobante"),
            weight=0.4,
        ),
    ),
    exclusions=(
        TextAbsenceSignal(
            signal_id="no_comprobante_de_pago",
            phrases=("comprobante de pago",),
            region=_FULL_PAGE,
        ),
        TextAbsenceSignal(
            signal_id="no_transferiste_upper",
            phrases=("transferiste",),
            region=_UPPER_ACTION,
        ),
    ),
)

ALL_UENO_PROFILES: tuple[IssuerProfile, ...] = (
    UENO_TRANSFER_SUMMARY,
    UENO_PAYMENT_RECEIPT,
    UENO_MOVEMENT_DETAIL,
)
