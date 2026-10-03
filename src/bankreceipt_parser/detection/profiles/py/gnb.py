"""GNB transfer receipt profiles."""
from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.shared import UPPER
from bankreceipt_parser.detection.signals.text import TextSignal

GNB_TRANSFER_SUCCESS = IssuerProfile(
    issuer="gnb",
    variant="transfer_success",
    establish_issuer=False,
    min_score=1.7,
    signals=(
        TextSignal("gnb_brand", ("gnb", "grupo nacion"), 0.9),
        TextSignal("transfer_success", ("transferencia", "exitosa"), 0.8, UPPER, True),
    ),
)

GNB_SPI_MOVEMENT = IssuerProfile(
    issuer="gnb",
    variant="spi_movement_detail",
    establish_issuer=True,
    min_score=1.7,
    required_signals=("gnb_institutional_reference", "spi_transfer_context"),
    signals=(
        TextSignal("gnb_institutional_reference", ("bgnbpyp",), 0.9),
        TextSignal(
            "spi_transfer_context",
            ("transferencia", "enviada", "spi"),
            0.9,
            match_all=True,
        ),
    ),
)

ALL_GNB_PROFILES = (GNB_TRANSFER_SUCCESS, GNB_SPI_MOVEMENT)
