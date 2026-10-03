"""ZETA transfer receipt profile."""
from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import FOOTER, UPPER
from bankreceipt_parser.detection.signals.text import TextSignal

ZETA_TRANSFER_RECEIPT = IssuerProfile(
    issuer="zeta",
    variant="transfer_receipt",
    establish_issuer=False,
    min_score=1.7,
    signals=(
        TextSignal("zeta_brand", ("zeta",), 0.9),
        TextSignal("transfer_sent", ("transferencia", "enviada"), 0.8, UPPER, True),
        TextSignal("share_receipt", ("compartir", "comprobante"), 0.4, FOOTER, True),
    ),
)
ALL_ZETA_PROFILES = (ZETA_TRANSFER_RECEIPT,)
