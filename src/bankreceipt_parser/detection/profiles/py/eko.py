"""EKO wallet transfer receipt profiles."""

from __future__ import annotations

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.signals.text import TextSignal

EKO_SEND_RECEIPT = IssuerProfile(
    issuer="eko",
    variant="send_receipt",
    min_score=2.2,
    establish_issuer=True,
    signals=(
        TextSignal("listo_header", ("listo",), 0.8),
        TextSignal("envio_heading", ("envio",), 0.8),
        TextSignal("share_receipt", ("compartir", "comprobante"), 0.9, match_all=True),
    ),
)

EKO_TRANSFER_DETAIL = IssuerProfile(
    issuer="eko",
    variant="transfer_detail",
    min_score=2.2,
    establish_issuer=True,
    signals=(
        TextSignal("detalle_header", ("detalle",), 0.7),
        TextSignal("enviaste_heading", ("enviaste",), 0.8),
        TextSignal("transferencia_section", ("transferencia",), 0.7),
        TextSignal("share_receipt", ("compartir", "comprobante"), 0.9, match_all=True),
    ),
)

ALL_EKO_PROFILES: tuple[IssuerProfile, ...] = (
    EKO_SEND_RECEIPT,
    EKO_TRANSFER_DETAIL,
)
