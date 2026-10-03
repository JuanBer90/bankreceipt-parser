"""ATLAS transfer receipt profile."""
from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import MIDDLE
from bankreceipt_parser.detection.signals.text import TextSignal

ATLAS_TRANSFER_RECEIPT = IssuerProfile(
    issuer="atlas",
    variant="transfer_receipt",
    establish_issuer=False,
    min_score=1.6,
    signals=(
        TextSignal("atlas_brand", ("atlas",), 0.9),
        TextSignal("transfer_sent", ("transferencia", "enviada"), 0.8, MIDDLE, True),
    ),
)
ALL_ATLAS_PROFILES = (ATLAS_TRANSFER_RECEIPT,)
