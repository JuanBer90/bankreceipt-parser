"""Layout order signals from structured OCR element positions."""

from __future__ import annotations

from dataclasses import dataclass

from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.lines import normalize_label


@dataclass(frozen=True)
class VerticalOrderSignal:
    """Require label tokens for ``upper_phrases`` to appear above ``lower_phrases``."""

    signal_id: str
    upper_phrases: tuple[str, ...]
    lower_phrases: tuple[str, ...]
    weight: float

    def evaluate(self, ocr: OCRResult) -> tuple[bool, float]:
        upper_ys = _phrase_ys(ocr, self.upper_phrases)
        lower_ys = _phrase_ys(ocr, self.lower_phrases)
        if not upper_ys or not lower_ys:
            return False, 0.0
        if min(upper_ys) < min(lower_ys):
            return True, self.weight
        return False, 0.0


def _phrase_ys(ocr: OCRResult, phrases: tuple[str, ...]) -> list[float]:
    normalized = tuple(normalize_label(p) for p in phrases)
    ys: list[float] = []
    for element in ocr.elements:
        token = normalize_label(element.text)
        if token in normalized or any(p in token for p in normalized):
            ys.append(element.bbox.y)
    return ys
