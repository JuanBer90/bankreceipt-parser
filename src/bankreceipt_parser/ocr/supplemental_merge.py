"""Merge a supplemental Tesseract pass into a primary PSM-6 OCR result."""

from __future__ import annotations

from statistics import median
from typing import Any

from bankreceipt_parser.ocr.normalize import normalize_ocr_text
from bankreceipt_parser.ocr.reading_order import join_ocr_lines, reconstruct_ocr_lines
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.ocr.tesseract_data import _elements_at_level

DEFAULT_MIN_CONFIDENCE = 60.0
DEFAULT_MIN_GAP_FRACTION = 0.35
DEFAULT_MIN_GAP_ABSOLUTE = 0.012
DEFAULT_IOU_DUPLICATE_THRESHOLD = 0.22
Y_CLUSTER_TOLERANCE = 0.018


def merge_supplemental_tesseract_pass(
    primary: OCRResult,
    supplemental_data: dict[str, list[Any]],
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> OCRResult:
    """
    Add line elements from a supplemental OCR pass when they fill vertical gaps
    in the primary line layout and are not duplicates of existing text.
    """
    supplemental_words = _elements_at_level(
        supplemental_data,
        level=5,
        image_width=primary.image_width,
        image_height=primary.image_height,
    )
    if not supplemental_words:
        return primary

    primary_lines = _line_elements(primary.elements)
    if len(primary_lines) < 2:
        return primary

    gaps = _vertical_gaps_between_lines(primary_lines)
    if not gaps:
        return primary

    candidates = [
        word
        for word in supplemental_words
        if _confidence_ok(word, min_confidence)
        and _center_y_in_gap(word, gaps)
        and not _duplicates_primary(word, primary.elements)
    ]
    if not candidates:
        return primary

    synthetic_lines = _group_words_into_lines(candidates)
    merged_elements = list(primary.elements)
    merged_elements.extend(synthetic_lines)
    merged_elements.sort(key=lambda element: (element.bbox.y, element.bbox.x))
    text = normalize_ocr_text(join_ocr_lines(reconstruct_ocr_lines(merged_elements)))
    return primary.model_copy(update={"text": text, "elements": merged_elements})


def _line_elements(elements: list[OCRTextElement]) -> list[OCRTextElement]:
    lines = [element for element in elements if element.level == "line" and element.text.strip()]
    return sorted(lines, key=lambda element: element.bbox.y)


def _vertical_gaps_between_lines(
    lines: list[OCRTextElement],
) -> list[tuple[float, float]]:
    heights = [line.bbox.height for line in lines if line.bbox.height > 0]
    median_height = median(heights) if heights else 0.01
    min_gap = max(DEFAULT_MIN_GAP_ABSOLUTE, median_height * DEFAULT_MIN_GAP_FRACTION)
    gaps: list[tuple[float, float]] = []
    for index in range(len(lines) - 1):
        upper = lines[index]
        lower = lines[index + 1]
        gap_start = upper.bbox.y + upper.bbox.height
        gap_end = lower.bbox.y
        if gap_end - gap_start >= min_gap:
            gaps.append((gap_start, gap_end))
    return gaps


def _center_y_in_gap(word: OCRTextElement, gaps: list[tuple[float, float]]) -> bool:
    center_y = word.bbox.y + word.bbox.height / 2
    return any(gap_start <= center_y <= gap_end for gap_start, gap_end in gaps)


def _confidence_ok(word: OCRTextElement, min_confidence: float) -> bool:
    if word.confidence is None:
        return False
    return word.confidence >= min_confidence


def _duplicates_primary(word: OCRTextElement, primary_elements: list[OCRTextElement]) -> bool:
    word_text = word.text.casefold().strip()
    if not word_text:
        return True
    for element in primary_elements:
        if not element.text.strip():
            continue
        element_text = element.text.casefold()
        if word_text == element_text:
            return True
        if _bbox_iou(word.bbox, element.bbox) >= DEFAULT_IOU_DUPLICATE_THRESHOLD:
            if word_text in element_text or element_text in word_text:
                return True
            tokens = element_text.split()
            if word_text in tokens:
                return True
        elif _same_text_row(word, element) and word_text in element_text.split():
            return True
    return False


def _same_text_row(a: OCRTextElement, b: OCRTextElement) -> bool:
    tolerance = max(a.bbox.height, b.bbox.height, 0.01) * 0.6
    center_a = a.bbox.y + a.bbox.height / 2
    center_b = b.bbox.y + b.bbox.height / 2
    return abs(center_a - center_b) <= tolerance


def _bbox_iou(a: NormalizedBoundingBox, b: NormalizedBoundingBox) -> float:
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx2, by2 = b.x + b.width, b.y + b.height
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    union = a.width * a.height + b.width * b.height - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _group_words_into_lines(words: list[OCRTextElement]) -> list[OCRTextElement]:
    ordered = sorted(words, key=lambda element: element.bbox.y)
    clusters: list[list[OCRTextElement]] = []
    current: list[OCRTextElement] = []
    anchor_y: float | None = None
    for word in ordered:
        if anchor_y is None or abs(word.bbox.y - anchor_y) <= Y_CLUSTER_TOLERANCE:
            current.append(word)
            anchor_y = word.bbox.y if anchor_y is None else (anchor_y + word.bbox.y) / 2
            continue
        clusters.append(current)
        current = [word]
        anchor_y = word.bbox.y
    if current:
        clusters.append(current)

    lines: list[OCRTextElement] = []
    for cluster in clusters:
        line = _synthetic_line_from_words(cluster)
        if line is not None:
            lines.append(line)
    return lines


def _synthetic_line_from_words(words: list[OCRTextElement]) -> OCRTextElement | None:
    ordered = sorted(words, key=lambda element: element.bbox.x)
    text = " ".join(part.text for part in ordered).strip()
    if not text:
        return None
    left = min(part.bbox.x for part in ordered)
    top = min(part.bbox.y for part in ordered)
    right = max(part.bbox.x + part.bbox.width for part in ordered)
    bottom = max(part.bbox.y + part.bbox.height for part in ordered)
    confidences = [part.confidence for part in ordered if part.confidence is not None]
    confidence = min(confidences) if confidences else None
    return OCRTextElement(
        text=text,
        confidence=confidence,
        bbox=NormalizedBoundingBox(
            x=left,
            y=top,
            width=max(right - left, 0.0),
            height=max(bottom - top, 0.0),
        ),
        level="line",
    )
