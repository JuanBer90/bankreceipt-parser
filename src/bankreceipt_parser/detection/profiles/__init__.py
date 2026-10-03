"""Issuer profile registry."""

from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.atlas import ALL_ATLAS_PROFILES
from bankreceipt_parser.detection.profiles.py.bancop import ALL_BANCOP_PROFILES
from bankreceipt_parser.detection.profiles.py.basa import ALL_BASA_PROFILES
from bankreceipt_parser.detection.profiles.py.bnf import ALL_BNF_PROFILES
from bankreceipt_parser.detection.profiles.py.comecipar import ALL_COMECIPAR_PROFILES
from bankreceipt_parser.detection.profiles.py.continental import ALL_CONTINENTAL_PROFILES
from bankreceipt_parser.detection.profiles.py.eclub import ALL_ECLUB_PROFILES
from bankreceipt_parser.detection.profiles.py.eko import ALL_EKO_PROFILES
from bankreceipt_parser.detection.profiles.py.familiar import ALL_FAMILIAR_PROFILES
from bankreceipt_parser.detection.profiles.py.financiera_pyj import ALL_FINANCIERA_PYJ_PROFILES
from bankreceipt_parser.detection.profiles.py.gnb import ALL_GNB_PROFILES
from bankreceipt_parser.detection.profiles.py.interfisa import ALL_INTERFISA_PROFILES
from bankreceipt_parser.detection.profiles.py.itau import ALL_ITAU_PROFILES
from bankreceipt_parser.detection.profiles.py.mango import ALL_MANGO_PROFILES
from bankreceipt_parser.detection.profiles.py.medalla_milagrosa import (
    ALL_MEDALLA_MILAGROSA_PROFILES,
)
from bankreceipt_parser.detection.profiles.py.sudameris import ALL_SUDAMERIS_PROFILES
from bankreceipt_parser.detection.profiles.py.ueno import ALL_UENO_PROFILES
from bankreceipt_parser.detection.profiles.py.vaquita import ALL_VAQUITA_PROFILES
from bankreceipt_parser.detection.profiles.py.zeta import ALL_ZETA_PROFILES

ALL_PROFILES: tuple[IssuerProfile, ...] = (
    ALL_UENO_PROFILES
    + ALL_ITAU_PROFILES
    + ALL_BASA_PROFILES
    + ALL_BNF_PROFILES
    + ALL_ATLAS_PROFILES
    + ALL_BANCOP_PROFILES
    + ALL_COMECIPAR_PROFILES
    + ALL_CONTINENTAL_PROFILES
    + ALL_ECLUB_PROFILES
    + ALL_EKO_PROFILES
    + ALL_FAMILIAR_PROFILES
    + ALL_MANGO_PROFILES
    + ALL_INTERFISA_PROFILES
    + ALL_FINANCIERA_PYJ_PROFILES
    + ALL_GNB_PROFILES
    + ALL_MEDALLA_MILAGROSA_PROFILES
    + ALL_SUDAMERIS_PROFILES
    + ALL_VAQUITA_PROFILES
    + ALL_ZETA_PROFILES
)

__all__ = ["ALL_PROFILES"]
