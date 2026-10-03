"""Shared normalized regions for transfer-receipt profile composition."""

from bankreceipt_parser.detection.signals.layout import NormalizedRegion

HEADER = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.12)
TOP = NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.15)
UPPER = NormalizedRegion(x=0.0, y=0.12, width=1.0, height=0.20)
MIDDLE = NormalizedRegion(x=0.0, y=0.25, width=1.0, height=0.40)
LOWER = NormalizedRegion(x=0.0, y=0.55, width=1.0, height=0.30)
FOOTER = NormalizedRegion(x=0.0, y=0.78, width=1.0, height=0.22)
