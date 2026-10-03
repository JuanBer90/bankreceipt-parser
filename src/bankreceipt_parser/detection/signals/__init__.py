"""Issuer detection signals (profile + legacy product lexicon)."""

from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.layout import NormalizedRegion, elements_in_region
from bankreceipt_parser.detection.signals.product_lexicon import (
    ISSUER_PRODUCT_SIGNALS,
    SignalHit,
    score_text_signals,
    summarize_signals,
)
from bankreceipt_parser.detection.signals.text import TextAbsenceSignal, TextSignal

__all__ = [
    "ColorRegionSignal",
    "ISSUER_PRODUCT_SIGNALS",
    "NormalizedRegion",
    "SignalHit",
    "TextAbsenceSignal",
    "TextSignal",
    "elements_in_region",
    "score_text_signals",
    "summarize_signals",
]
