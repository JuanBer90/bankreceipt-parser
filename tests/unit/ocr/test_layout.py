"""Layout profile tests."""

from __future__ import annotations

from bankreceipt_parser.ocr.layout import (
    VerticalRegion,
    build_layout_profile,
    vertical_region_for_y,
)
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def test_vertical_region_for_y_bands() -> None:
    assert vertical_region_for_y(0.05) == VerticalRegion.HEADER
    assert vertical_region_for_y(0.2) == VerticalRegion.UPPER
    assert vertical_region_for_y(0.5) == VerticalRegion.MIDDLE
    assert vertical_region_for_y(0.9) == VerticalRegion.FOOTER


def test_build_layout_profile_region_sequence() -> None:
    ocr = OCRResult(
        text="a\nb\nc",
        image_width=1000,
        image_height=1000,
        elements=[
            OCRTextElement(
                text="Titulo",
                bbox=NormalizedBoundingBox(x=0.1, y=0.05, width=0.8, height=0.05),
                line_index=1,
            ),
            OCRTextElement(
                text="Monto",
                bbox=NormalizedBoundingBox(x=0.1, y=0.4, width=0.5, height=0.05),
                line_index=2,
            ),
            OCRTextElement(
                text="Red",
                bbox=NormalizedBoundingBox(x=0.1, y=0.9, width=0.5, height=0.04),
                line_index=3,
            ),
        ],
    )
    profile = build_layout_profile(ocr)
    assert VerticalRegion.HEADER in profile.region_sequence
    assert VerticalRegion.FOOTER in profile.region_sequence
