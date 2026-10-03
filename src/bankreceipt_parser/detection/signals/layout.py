"""Normalized layout regions for issuer profile signals."""

from __future__ import annotations

from dataclasses import dataclass

from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRTextElement


@dataclass(frozen=True)
class NormalizedRegion:
    """Axis-aligned rectangle in normalized image coordinates (0.0–1.0)."""

    x: float
    y: float
    width: float
    height: float

    def contains_point(self, x: float, y: float) -> bool:
        return (
            self.x <= x <= self.x + self.width
            and self.y <= y <= self.y + self.height
        )

    def contains_bbox_center(self, bbox: NormalizedBoundingBox) -> bool:
        cx = bbox.x + bbox.width / 2
        cy = bbox.y + bbox.height / 2
        return self.contains_point(cx, cy)


def elements_in_region(
    elements: tuple[OCRTextElement, ...] | list[OCRTextElement],
    region: NormalizedRegion,
) -> tuple[OCRTextElement, ...]:
    """OCR elements whose bounding-box center falls inside ``region``."""
    return tuple(el for el in elements if region.contains_bbox_center(el.bbox))
