"""VAQUITA yellow transfer-receipt profile."""

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import TOP
from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.text import TextSignal
from bankreceipt_parser.models.issuer import Issuer

VAQUITA_YELLOW_TRANSFER = IssuerProfile(
    issuer=Issuer.VAQUITA,
    variant="yellow_transfer",
    min_score=2.3,
    signals=(
        ColorRegionSignal("yellow_header", TOP, (240, 205, 40), 55.0, 0.75, 0.9),
        TextSignal("vaquita_brand", ("vaquita",), 0.8),
        TextSignal("receipt_header", ("comprobante",), 0.6, TOP),
    ),
)

ALL_VAQUITA_PROFILES = (VAQUITA_YELLOW_TRANSFER,)
