"""BANCOP transfer screen profile, established from structure plus visual shell."""

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import TOP
from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.text import TextSignal

BANCOP_TRANSFER_SCREEN = IssuerProfile(
    issuer="bancop",
    variant="transfer_screen",
    min_score=2.4,
    signals=(
        ColorRegionSignal("blue_transfer_shell", TOP, (0, 112, 176), 65.0, 0.38, 0.9),
        TextSignal("transferencias_header", ("transferencias",), 0.8, TOP),
        TextSignal("operation_done_header", ("operacion", "realizada"), 0.8, TOP, True),
        TextSignal("share_receipt", ("compartir", "comprobante"), 0.8),
    ),
    required_signals=("blue_transfer_shell",),
)

ALL_BANCOP_PROFILES = (BANCOP_TRANSFER_SCREEN,)
