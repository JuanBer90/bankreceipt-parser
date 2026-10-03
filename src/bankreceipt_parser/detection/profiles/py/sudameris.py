"""Sudameris branded transfer profile."""
from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import UPPER
from bankreceipt_parser.detection.signals.text import TextSignal

SUDAMERIS_TRANSFER_RECEIPT = IssuerProfile(
    issuer="sudameris",
    variant="transfer_receipt",
    establish_issuer=False,
    min_score=1.3,
    signals=(
        TextSignal("sudameris_brand", ("sudameris",), 0.9),
        TextSignal("transfer_context", ("transferencia",), 0.5, UPPER),
    ),
)
ALL_SUDAMERIS_PROFILES = (SUDAMERIS_TRANSFER_RECEIPT,)
