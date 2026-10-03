"""Continental transfer receipt profile."""
from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import UPPER
from bankreceipt_parser.detection.signals.text import TextSignal

CONTINENTAL_TRANSFER_RECEIPT = IssuerProfile(
    issuer="continental",
    variant="transfer_receipt",
    establish_issuer=False,
    min_score=1.7,
    signals=(
        TextSignal("continental_brand", ("continental",), 0.9),
        TextSignal("receipt_transfer", ("comprobante", "transferencia"), 0.8, UPPER, True),
    ),
)
ALL_CONTINENTAL_PROFILES = (CONTINENTAL_TRANSFER_RECEIPT,)
