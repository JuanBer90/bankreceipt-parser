"""Medalla Milagrosa transfer-operation profile."""

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import LOWER, UPPER
from bankreceipt_parser.detection.signals.text import TextSignal

MEDALLA_MILAGROSA_TRANSFER_OPERATION = IssuerProfile(
    issuer="medalla_milagrosa",
    variant="transfer_operation",
    min_score=2.4,
    signals=(
        TextSignal("medalla_brand", ("medalla milagrosa",), 0.8),
        TextSignal("transfer_operation", ("transferencia", "operacion"), 0.8, UPPER, True),
        TextSignal("receipt_transfer", ("comprobante", "transferencia"), 0.8, LOWER, True),
    ),
)

ALL_MEDALLA_MILAGROSA_PROFILES = (MEDALLA_MILAGROSA_TRANSFER_OPERATION,)
