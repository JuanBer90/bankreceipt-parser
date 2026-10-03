"""Map detected issuer keys to concrete parsers."""

from __future__ import annotations

from typing import cast

from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.parsers.base import StructuredReceiptParser
from bankreceipt_parser.parsers.py.atlas import AtlasReceiptParser
from bankreceipt_parser.parsers.py.bancop import BancopReceiptParser
from bankreceipt_parser.parsers.py.basa import BasaReceiptParser
from bankreceipt_parser.parsers.py.bnf import BnfReceiptParser
from bankreceipt_parser.parsers.py.comecipar import ComeciparReceiptParser
from bankreceipt_parser.parsers.py.continental import ContinentalReceiptParser
from bankreceipt_parser.parsers.py.eclub import EclubReceiptParser
from bankreceipt_parser.parsers.py.eko import EkoReceiptParser
from bankreceipt_parser.parsers.py.familiar import FamiliarReceiptParser
from bankreceipt_parser.parsers.py.financiera_pyj import FinancieraPyjReceiptParser
from bankreceipt_parser.parsers.py.gnb import GnbReceiptParser
from bankreceipt_parser.parsers.py.interfisa import InterfisaReceiptParser
from bankreceipt_parser.parsers.py.itau import ItauReceiptParser
from bankreceipt_parser.parsers.py.mango import MangoReceiptParser
from bankreceipt_parser.parsers.py.medalla_milagrosa import MedallaMilagrosaReceiptParser
from bankreceipt_parser.parsers.py.sudameris import SudamerisReceiptParser
from bankreceipt_parser.parsers.py.ueno import UenoReceiptParser
from bankreceipt_parser.parsers.py.vaquita import VaquitaReceiptParser
from bankreceipt_parser.parsers.py.zeta import ZetaReceiptParser

_PARSERS: dict[str, StructuredReceiptParser] = {
    Issuer.UENO.value: cast(StructuredReceiptParser, UenoReceiptParser()),
    Issuer.BNF.value: cast(StructuredReceiptParser, BnfReceiptParser()),
    Issuer.ITAU.value: cast(StructuredReceiptParser, ItauReceiptParser()),
    Issuer.GNB.value: cast(StructuredReceiptParser, GnbReceiptParser()),
    Issuer.ATLAS.value: cast(StructuredReceiptParser, AtlasReceiptParser()),
    Issuer.BANCOP.value: cast(StructuredReceiptParser, BancopReceiptParser()),
    Issuer.BASA.value: cast(StructuredReceiptParser, BasaReceiptParser()),
    Issuer.CONTINENTAL.value: cast(StructuredReceiptParser, ContinentalReceiptParser()),
    Issuer.COMECIPAR.value: cast(StructuredReceiptParser, ComeciparReceiptParser()),
    Issuer.ECLUB.value: cast(StructuredReceiptParser, EclubReceiptParser()),
    Issuer.EKO.value: cast(StructuredReceiptParser, EkoReceiptParser()),
    Issuer.FAMILIAR.value: cast(StructuredReceiptParser, FamiliarReceiptParser()),
    Issuer.MANGO.value: cast(StructuredReceiptParser, MangoReceiptParser()),
    Issuer.INTERFISA.value: cast(StructuredReceiptParser, InterfisaReceiptParser()),
    Issuer.FINANCIERA_PYJ.value: cast(StructuredReceiptParser, FinancieraPyjReceiptParser()),
    Issuer.MEDALLA_MILAGROSA.value: cast(
        StructuredReceiptParser, MedallaMilagrosaReceiptParser()
    ),
    Issuer.SUDAMERIS.value: cast(StructuredReceiptParser, SudamerisReceiptParser()),
    Issuer.VAQUITA.value: cast(StructuredReceiptParser, VaquitaReceiptParser()),
    Issuer.ZETA.value: cast(StructuredReceiptParser, ZetaReceiptParser()),
}


def parser_for_issuer(issuer: str | None) -> StructuredReceiptParser | None:
    """Return a parser implementation when available."""
    if issuer is None:
        return None
    return _PARSERS.get(issuer)
