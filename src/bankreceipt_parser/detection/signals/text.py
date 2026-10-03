"""Text-based issuer profile signals."""

from __future__ import annotations

from dataclasses import dataclass

from bankreceipt_parser.detection.signals.layout import NormalizedRegion, elements_in_region
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.lines import normalize_label


@dataclass(frozen=True)
class TextSignal:
    """
    Match normalized phrases in OCR text, optionally restricted to a layout region.

    When ``match_all`` is true, every phrase must appear among elements in the region
    (or anywhere in the document if ``region`` is omitted).
    """

    signal_id: str
    phrases: tuple[str, ...]
    weight: float
    region: NormalizedRegion | None = None
    match_all: bool = False

    def evaluate(self, ocr: OCRResult) -> tuple[bool, float]:
        normalized_phrases = tuple(normalize_label(p) for p in self.phrases)
        if not normalized_phrases:
            return False, 0.0

        if self.region is None:
            full = normalize_label(ocr.text)
            if self.match_all:
                matched = all(p in full for p in normalized_phrases)
            else:
                matched = any(p in full for p in normalized_phrases)
            return matched, self.weight if matched else 0.0

        scoped = elements_in_region(ocr.elements, self.region)
        scoped_text = " ".join(normalize_label(el.text) for el in scoped)
        if self.match_all:
            matched = all(
                any(p in normalize_label(el.text) for el in scoped) for p in normalized_phrases
            )
        else:
            matched = any(p in scoped_text for p in normalized_phrases)
        return matched, self.weight if matched else 0.0


@dataclass(frozen=True)
class TextAbsenceSignal:
    """Veto when forbidden phrases appear inside a layout region."""

    signal_id: str
    phrases: tuple[str, ...]
    region: NormalizedRegion
    weight: float = 0.0

    def evaluate(self, ocr: OCRResult) -> tuple[bool, float]:
        """Return (exclusion_triggered, 0.0). ``exclusion_triggered`` means profile is vetoed."""
        scoped = elements_in_region(ocr.elements, self.region)
        scoped_text = " ".join(normalize_label(el.text) for el in scoped)
        normalized = tuple(normalize_label(p) for p in self.phrases)
        triggered = any(p in scoped_text for p in normalized)
        return triggered, 0.0
