"""
BNF (Banco Nacional de Fomento) issuer profiles.

Two transfer receipt layouts: a self-establishing card screen without BNF in OCR,
and an operation-success detail with explicit BNF branding. Destination bank names
are never used as issuer evidence.
"""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import TOP
from bankreceipt_parser.detection.signals.layout import NormalizedRegion
from bankreceipt_parser.detection.signals.order import VerticalOrderSignal
from bankreceipt_parser.detection.signals.text import TextSignal
from bankreceipt_parser.models.issuer import Issuer

# Card field labels span most of the screen below the header band.
_CARD_BODY = NormalizedRegion(x=0.0, y=0.25, width=1.0, height=0.75)

BNF_TRANSFER_SENT_CARD = IssuerProfile(
    issuer=Issuer.BNF,
    variant="transfer_sent_card",
    min_score=4.0,
    establish_issuer=True,
    required_signals=(
        "destinatario_label",
        "entidad_destino_label",
        "tipo_cuenta_label",
    ),
    signals=(
        TextSignal(
            signal_id="destinatario_label",
            phrases=("destinatario",),
            weight=0.7,
            region=_CARD_BODY,
        ),
        TextSignal(
            signal_id="entidad_destino_label",
            phrases=("entidad", "destino"),
            weight=1.0,
            region=_CARD_BODY,
            match_all=True,
        ),
        TextSignal(
            signal_id="tipo_cuenta_label",
            phrases=("tipo", "cuenta"),
            weight=0.9,
            region=_CARD_BODY,
            match_all=True,
        ),
        TextSignal(
            signal_id="fecha_y_hora_label",
            phrases=("fecha", "hora"),
            weight=0.8,
            region=_CARD_BODY,
            match_all=True,
        ),
        TextSignal(
            signal_id="transferencia_enviada_header",
            phrases=("transferencia enviada",),
            weight=0.5,
            region=TOP,
        ),
        TextSignal(
            signal_id="nro_de_comprobante",
            phrases=("nro. de comprobante", "nro de comprobante"),
            weight=0.5,
            region=_CARD_BODY,
        ),
        VerticalOrderSignal(
            signal_id="order_destinatario_before_entidad",
            upper_phrases=("destinatario",),
            lower_phrases=("entidad", "destino"),
            weight=0.8,
        ),
        VerticalOrderSignal(
            signal_id="order_entidad_before_tipo_cuenta",
            upper_phrases=("entidad",),
            lower_phrases=("tipo",),
            weight=0.6,
        ),
    ),
)

BNF_OPERATION_SUCCESS_RECEIPT = IssuerProfile(
    issuer=Issuer.BNF,
    variant="operation_success_receipt",
    min_score=2.8,
    establish_issuer=True,
    required_signals=(
        "operacion_exitosa_title",
        "detalle_sip_otros_bancos",
    ),
    signals=(
        TextSignal(
            signal_id="operacion_exitosa_title",
            phrases=("operacion exitosa", "operación exitosa"),
            weight=1.0,
        ),
        TextSignal(
            signal_id="detalle_sip_otros_bancos",
            phrases=(
                "transferencia a cuentas de otros bancos",
                "otros bancos",
            ),
            weight=1.0,
        ),
        TextSignal(
            signal_id="fecha_de_operacion",
            phrases=("fecha de operacion", "fecha de operación"),
            weight=0.9,
        ),
        TextSignal(
            signal_id="nro_comprobante",
            phrases=("nro. comprobante", "nro comprobante"),
            weight=0.7,
        ),
        TextSignal(
            signal_id="enviado_por_label",
            phrases=("enviado por",),
            weight=0.8,
        ),
        TextSignal(
            signal_id="banco_cooperativa_label",
            phrases=("banco", "cooperativa"),
            weight=0.8,
            match_all=True,
        ),
        TextSignal(
            signal_id="bnf_brand_corroboration",
            phrases=("bnf",),
            weight=0.4,
        ),
    ),
)

ALL_BNF_PROFILES: tuple[IssuerProfile, ...] = (
    BNF_TRANSFER_SENT_CARD,
    BNF_OPERATION_SUCCESS_RECEIPT,
)
