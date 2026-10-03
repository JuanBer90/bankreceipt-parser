"""ECLUB transfer screen profile using independent shell and status signals."""

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import MIDDLE, TOP, UPPER
from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.text import TextSignal

ECLUB_TRANSFER_SCREEN = IssuerProfile(
    issuer="eclub",
    variant="transfer_screen",
    min_score=2.2,
    signals=(
        ColorRegionSignal("magenta_transfer_shell", TOP, (200, 0, 64), 65.0, 0.7, 0.9),
        TextSignal("transfer_done", ("transferencia", "realizada"), 0.8, UPPER, True),
        TextSignal("status_field", ("estado",), 0.5, MIDDLE),
    ),
)

ALL_ECLUB_PROFILES = (ECLUB_TRANSFER_SCREEN,)
