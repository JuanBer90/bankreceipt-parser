"""Convert Tesseract ``image_to_data`` output into structured OCR models."""

from __future__ import annotations

from typing import Any

from bankreceipt_parser.ocr.normalize import normalize_ocr_text
from bankreceipt_parser.ocr.reading_order import join_ocr_lines, reconstruct_ocr_lines
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def build_ocr_result_from_tesseract_data(
    *,
    data: dict[str, list[Any]],
    image_width: int,
    image_height: int,
    warnings: tuple[str, ...] = (),
) -> OCRResult:
    """Build an OCRResult from a Tesseract data dictionary."""
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")

    line_elements = _elements_at_level(
        data,
        level=4,
        image_width=image_width,
        image_height=image_height,
    )
    word_elements = _elements_at_level(
        data,
        level=5,
        image_width=image_width,
        image_height=image_height,
    )
    empty_line_keys = _empty_tesseract_line_keys(data)
    if empty_line_keys and word_elements:
        line_elements = _inject_lines_from_words(
            line_elements,
            word_elements,
            only_keys=empty_line_keys,
        )
    if not line_elements:
        line_elements = word_elements

    text = normalize_ocr_text(join_ocr_lines(reconstruct_ocr_lines(line_elements)))
    return OCRResult(
        text=text,
        elements=line_elements,
        image_width=image_width,
        image_height=image_height,
        warnings=warnings,
    )


def _elements_at_level(
    data: dict[str, list[Any]],
    *,
    level: int,
    image_width: int,
    image_height: int,
) -> list[OCRTextElement]:
    count = len(data.get("text", []))
    elements: list[OCRTextElement] = []
    for index in range(count):
        if int(data["level"][index]) != level:
            continue
        raw_text = str(data["text"][index]).strip()
        if not raw_text:
            continue
        conf_value = float(data["conf"][index])
        confidence = None if conf_value < 0 else conf_value
        left = int(data["left"][index])
        top = int(data["top"][index])
        width = int(data["width"][index])
        height = int(data["height"][index])
        word_nums = data.get("word_num")
        word_num = int(word_nums[index]) if word_nums is not None else 0
        par_nums = data.get("par_num")
        paragraph_index = int(par_nums[index]) if par_nums is not None else None
        elements.append(
            OCRTextElement(
                text=raw_text,
                confidence=confidence,
                bbox=_normalize_bbox(left, top, width, height, image_width, image_height),
                line_index=int(data["line_num"][index]),
                block_index=int(data["block_num"][index]),
                paragraph_index=paragraph_index,
                word_index=word_num if level == 5 and word_num > 0 else None,
                level="line" if level == 4 else "word",
            )
        )
    return elements


def _line_key(element: OCRTextElement) -> tuple[int | None, int | None, int | None]:
    return (element.block_index, element.paragraph_index, element.line_index)


def _empty_tesseract_line_keys(
    data: dict[str, list[Any]],
) -> set[tuple[int | None, int | None, int | None]]:
    count = len(data.get("text", []))
    keys: set[tuple[int | None, int | None, int | None]] = set()
    for index in range(count):
        if int(data["level"][index]) != 4:
            continue
        if str(data["text"][index]).strip():
            continue
        par_nums = data.get("par_num")
        paragraph_index = int(par_nums[index]) if par_nums is not None else None
        keys.add(
            (
                int(data["block_num"][index]),
                paragraph_index,
                int(data["line_num"][index]),
            )
        )
    return keys


def _inject_lines_from_words(
    line_elements: list[OCRTextElement],
    word_elements: list[OCRTextElement],
    *,
    only_keys: set[tuple[int | None, int | None, int | None]],
) -> list[OCRTextElement]:
    """Add synthetic line elements when Tesseract omits line-level text but words exist."""
    if not word_elements or not only_keys:
        return line_elements
    covered = {_line_key(element) for element in line_elements}
    grouped: dict[tuple[int | None, int | None, int | None], list[OCRTextElement]] = {}
    for word in word_elements:
        key = _line_key(word)
        if key in covered or key not in only_keys:
            continue
        grouped.setdefault(key, []).append(word)
    if not grouped:
        return line_elements
    merged = list(line_elements)
    for _key, words in grouped.items():
        ordered = sorted(words, key=lambda element: element.bbox.x)
        text = " ".join(part.text for part in ordered).strip()
        if not text:
            continue
        left = min(part.bbox.x for part in ordered)
        top = min(part.bbox.y for part in ordered)
        right = max(part.bbox.x + part.bbox.width for part in ordered)
        bottom = max(part.bbox.y + part.bbox.height for part in ordered)
        confidences = [part.confidence for part in ordered if part.confidence is not None]
        confidence = min(confidences) if confidences else None
        merged.append(
            OCRTextElement(
                text=text,
                confidence=confidence,
                bbox=NormalizedBoundingBox(
                    x=left,
                    y=top,
                    width=max(right - left, 0.0),
                    height=max(bottom - top, 0.0),
                ),
                line_index=ordered[0].line_index,
                block_index=ordered[0].block_index,
                paragraph_index=ordered[0].paragraph_index,
                level="line",
            )
        )
    return sorted(merged, key=lambda element: (element.bbox.y, element.bbox.x))


def _normalize_bbox(
    left: int,
    top: int,
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> NormalizedBoundingBox:
    return NormalizedBoundingBox(
        x=left / image_width,
        y=top / image_height,
        width=width / image_width,
        height=height / image_height,
    )
