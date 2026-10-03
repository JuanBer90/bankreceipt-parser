"""COMECIPAR transfer-success profile."""

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import FOOTER, HEADER, UPPER
from bankreceipt_parser.detection.signals.text import TextSignal

COMECIPAR_TRANSFER_SUCCESS = IssuerProfile(
    issuer="comecipar",
    variant="transfer_success",
    min_score=2.8,
    signals=(
        TextSignal("comecipar_brand", ("comecipar", "coomecipar"), 0.8),
        TextSignal("header_transfer", ("transferencia",), 0.7, HEADER),
        TextSignal("upper_success", ("transferencia", "exitosa"), 0.8, UPPER, True),
        TextSignal("footer_transfer", ("transferencia",), 0.7, FOOTER),
    ),
)

ALL_COMECIPAR_PROFILES = (COMECIPAR_TRANSFER_SUCCESS,)
