"""Layout helpers derived from structured OCR (resolution-independent)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from bankreceipt_parser.ocr.structure import OCRResult


class VerticalRegion(StrEnum):
    """Normalized vertical bands on the receipt image."""

    HEADER = "header"
    UPPER = "upper"
    MIDDLE = "middle"
    LOWER = "lower"
    FOOTER = "footer"


class LayoutProfile(BaseModel):
    """Coarse layout fingerprint for issuer research and future detection."""

    region_sequence: tuple[VerticalRegion, ...] = ()
    line_count_by_region: dict[str, int] = Field(default_factory=dict)
    top_label_tokens: tuple[str, ...] = ()


def vertical_region_for_y(y: float) -> VerticalRegion:
    """Map a normalized y coordinate to a vertical band."""
    if y < 0.12:
        return VerticalRegion.HEADER
    if y < 0.32:
        return VerticalRegion.UPPER
    if y < 0.58:
        return VerticalRegion.MIDDLE
    if y < 0.82:
        return VerticalRegion.LOWER
    return VerticalRegion.FOOTER


def build_layout_profile(ocr: OCRResult, *, max_top_labels: int = 6) -> LayoutProfile:
    """Summarize OCR element positions without using absolute pixels."""
    lines = list(ocr.elements)
    if not lines:
        return LayoutProfile()

    ordered = sorted(lines, key=lambda el: (el.bbox.y, el.bbox.x))
    region_sequence: list[VerticalRegion] = []
    counts: dict[str, int] = {}
    top_labels: list[str] = []

    for element in ordered:
        region = vertical_region_for_y(element.bbox.y)
        region_sequence.append(region)
        key = region.value
        counts[key] = counts.get(key, 0) + 1
        if (
            region in {VerticalRegion.HEADER, VerticalRegion.UPPER}
            and len(top_labels) < max_top_labels
        ):
            token = _safe_label_token(element.text)
            if token:
                top_labels.append(token)

    compressed = _compress_region_sequence(region_sequence)
    return LayoutProfile(
        region_sequence=compressed,
        line_count_by_region=counts,
        top_label_tokens=tuple(top_labels),
    )


def _compress_region_sequence(regions: list[VerticalRegion]) -> tuple[VerticalRegion, ...]:
    compressed: list[VerticalRegion] = []
    for region in regions:
        if not compressed or compressed[-1] != region:
            compressed.append(region)
    return tuple(compressed)


def _safe_label_token(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return ""
    if len(cleaned) > 48:
        cleaned = cleaned[:48]
    return cleaned
