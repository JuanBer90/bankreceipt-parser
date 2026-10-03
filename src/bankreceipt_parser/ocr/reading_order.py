"""Reconstruct reading-order lines from structured OCR elements.

Engines should populate ``block_index``, ``paragraph_index``, ``line_index``, and
``word_index`` when available (Tesseract ``image_to_data``). When that full
structural metadata is present on every element, lines are grouped by
``(block_index, paragraph_index, line_index)`` and words ordered by ``word_index``
or ``bbox.x`` (strict per-line rule). Otherwise geometry is used without treating
``line_index`` as a global identity.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

from bankreceipt_parser.ocr.structure import OCRTextElement

StructuralLineKey = tuple[int | None, int | None, int | None]


def join_ocr_lines(lines: Iterable[str]) -> str:
    """Join reconstructed lines with newlines."""
    return "\n".join(line for line in lines if line.strip())


def reconstruct_ocr_lines(
    elements: Sequence[OCRTextElement],
    *,
    y_tolerance: float = 0.018,
) -> list[str]:
    """Build human reading-order lines from OCR elements."""
    active = [element for element in elements if element.text.strip()]
    if not active:
        return []

    line_level = [element for element in active if element.level == "line"]
    word_level = [element for element in active if element.level != "line"]

    if line_level and not word_level:
        return _lines_from_line_level(line_level)

    if word_level and not line_level:
        return _lines_from_word_level(word_level, y_tolerance=y_tolerance)

    positioned: list[tuple[float, float, str]] = []
    for element in line_level:
        text = element.text.strip()
        if text:
            positioned.append((element.bbox.y, element.bbox.x, text))
    word_groups = _group_word_elements(word_level, y_tolerance=y_tolerance)
    for group in sorted(word_groups, key=_group_sort_key):
        line = _join_group(group)
        if line:
            y_value, x_value = _group_position(group)
            positioned.append((y_value, x_value, line))
    ordered = sorted(positioned, key=lambda item: (item[0], item[1]))
    return [text for _, _, text in ordered]


def _lines_from_line_level(elements: list[OCRTextElement]) -> list[str]:
    if _has_structural_complete(elements):
        ordered = sorted(
            elements,
            key=lambda el: (
                el.block_index,
                el.paragraph_index,
                el.line_index,
                el.bbox.y,
                el.bbox.x,
            ),
        )
    else:
        ordered = sorted(elements, key=lambda el: (el.bbox.y, el.bbox.x))
    return [element.text.strip() for element in ordered if element.text.strip()]


def _lines_from_word_level(elements: list[OCRTextElement], *, y_tolerance: float) -> list[str]:
    groups = _group_word_elements(elements, y_tolerance=y_tolerance)
    ordered_groups = sorted(groups, key=_group_sort_key)
    lines: list[str] = []
    for group in ordered_groups:
        line = _join_group(group)
        if line:
            lines.append(line)
    return lines


def _group_word_elements(
    elements: list[OCRTextElement],
    *,
    y_tolerance: float,
) -> list[list[OCRTextElement]]:
    if _has_structural_complete(elements):
        buckets: dict[StructuralLineKey, list[OCRTextElement]] = defaultdict(list)
        for element in elements:
            key = (element.block_index, element.paragraph_index, element.line_index)
            buckets[key].append(element)
        return list(buckets.values())

    clusters = _cluster_by_y(elements, y_tolerance=y_tolerance)
    groups: list[list[OCRTextElement]] = []
    for cluster in clusters:
        groups.extend(_split_cluster_by_structure(cluster))
    return groups


def _has_structural_complete(elements: Sequence[OCRTextElement]) -> bool:
    return all(
        element.block_index is not None
        and element.paragraph_index is not None
        and element.line_index is not None
        for element in elements
    )


def _cluster_by_y(
    elements: list[OCRTextElement], *, y_tolerance: float
) -> list[list[OCRTextElement]]:
    ordered = sorted(elements, key=lambda el: el.bbox.y)
    clusters: list[list[OCRTextElement]] = []
    current: list[OCRTextElement] = []
    anchor_y: float | None = None

    for element in ordered:
        if anchor_y is None or abs(element.bbox.y - anchor_y) <= y_tolerance:
            current.append(element)
            anchor_y = element.bbox.y if anchor_y is None else (anchor_y + element.bbox.y) / 2
            continue
        clusters.append(current)
        current = [element]
        anchor_y = element.bbox.y

    if current:
        clusters.append(current)
    return clusters


def _split_cluster_by_structure(cluster: list[OCRTextElement]) -> list[list[OCRTextElement]]:
    buckets: dict[StructuralLineKey, list[OCRTextElement]] = defaultdict(list)
    for element in cluster:
        key = (element.block_index, element.paragraph_index, element.line_index)
        buckets[key].append(element)
    return list(buckets.values())


def _valid_word_index(word_index: int | None) -> bool:
    return word_index is not None and word_index > 0


def _sort_intra_line(group: list[OCRTextElement]) -> list[OCRTextElement]:
    if all(_valid_word_index(element.word_index) for element in group):
        return sorted(group, key=lambda el: el.word_index or 0)
    return sorted(group, key=lambda el: el.bbox.x)


def _join_group(group: list[OCRTextElement]) -> str:
    sorted_group = _sort_intra_line(group)
    return " ".join(element.text.strip() for element in sorted_group if element.text.strip())


def _group_sort_key(group: list[OCRTextElement]) -> tuple[int, int, int, float, float]:
    if _has_structural_complete(group):
        sample = min(
            group,
            key=lambda el: (el.block_index or 0, el.paragraph_index or 0, el.line_index or 0),
        )
        return (
            sample.block_index or 0,
            sample.paragraph_index or 0,
            sample.line_index or 0,
            _group_position(group)[0],
            _group_position(group)[1],
        )
    y_value, x_value = _group_position(group)
    return (0, 0, 0, y_value, x_value)


def _group_position(group: list[OCRTextElement]) -> tuple[float, float]:
    ys = [element.bbox.y for element in group]
    xs = [element.bbox.x for element in group]
    return (min(ys), min(xs))
