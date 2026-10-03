"""Tests for OCR reading-order reconstruction."""

from __future__ import annotations

from bankreceipt_parser.ocr.reading_order import reconstruct_ocr_lines
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRTextElement


def _bbox(x: float, y: float) -> NormalizedBoundingBox:
    return NormalizedBoundingBox(x=x, y=y, width=0.1, height=0.02)


def _word(
    text: str,
    *,
    x: float,
    y: float,
    word_index: int | None,
    block_index: int = 1,
    paragraph_index: int = 1,
    line_index: int = 1,
) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=_bbox(x, y),
        block_index=block_index,
        paragraph_index=paragraph_index,
        line_index=line_index,
        word_index=word_index,
        level="word",
    )


def test_same_line_different_y_orders_by_word_index() -> None:
    elements = [
        _word("a", x=0.20, y=0.263, word_index=1),
        _word("Ejemplo", x=0.25, y=0.259, word_index=2),
        _word("Demo", x=0.40, y=0.259, word_index=3),
    ]
    assert reconstruct_ocr_lines(elements) == ["a Ejemplo Demo"]


def test_bank_name_same_structural_line() -> None:
    elements = [
        _word("UENO", x=0.1, y=0.30, word_index=1),
        _word("BANK", x=0.2, y=0.301, word_index=2),
        _word("S.A.", x=0.35, y=0.299, word_index=3),
    ]
    assert reconstruct_ocr_lines(elements) == ["UENO BANK S.A."]


def test_distinct_structural_lines_not_merged() -> None:
    elements = [
        _word("Alpha", x=0.1, y=0.20, word_index=1, line_index=1),
        _word("Beta", x=0.2, y=0.21, word_index=1, line_index=2),
    ]
    assert reconstruct_ocr_lines(elements) == ["Alpha", "Beta"]


def test_without_line_index_clusters_y_orders_by_x() -> None:
    elements = [
        OCRTextElement(text="Ejemplo", bbox=_bbox(0.25, 0.259), level="word"),
        OCRTextElement(text="a", bbox=_bbox(0.20, 0.263), level="word"),
    ]
    assert reconstruct_ocr_lines(elements) == ["a Ejemplo"]


def test_line_level_elements_preserve_whole_line_text() -> None:
    elements = [
        OCRTextElement(
            text="Comprobante",
            bbox=_bbox(0.1, 0.1),
            line_index=1,
            block_index=1,
            paragraph_index=1,
            level="line",
        ),
        OCRTextElement(
            text="Transferencia",
            bbox=_bbox(0.1, 0.2),
            line_index=2,
            block_index=1,
            paragraph_index=1,
            level="line",
        ),
    ]
    assert reconstruct_ocr_lines(elements) == ["Comprobante", "Transferencia"]


def test_fixture_style_one_element_per_line() -> None:
    lines = ["ueno bank", "Comprobante de transferencia", "25.000"]
    elements = [
        OCRTextElement(
            text=line,
            bbox=_bbox(0.1, 0.05 + index * 0.05),
            line_index=index + 1,
        )
        for index, line in enumerate(lines)
    ]
    assert reconstruct_ocr_lines(elements) == lines


def test_repeated_line_index_different_blocks_stay_separate() -> None:
    elements = [
        _word("BlockOne", x=0.1, y=0.2, word_index=1, block_index=1, line_index=1),
        _word("BlockTwo", x=0.1, y=0.2, word_index=1, block_index=2, line_index=1),
    ]
    assert reconstruct_ocr_lines(elements) == ["BlockOne", "BlockTwo"]


def test_partial_metadata_repeated_line_index_not_merged() -> None:
    elements = [
        OCRTextElement(
            text="Top",
            bbox=_bbox(0.1, 0.10),
            line_index=1,
            level="word",
        ),
        OCRTextElement(
            text="Bottom",
            bbox=_bbox(0.1, 0.30),
            line_index=1,
            level="word",
        ),
    ]
    assert reconstruct_ocr_lines(elements) == ["Top", "Bottom"]


def test_incomplete_word_index_sorts_entire_line_by_x() -> None:
    elements = [
        _word("Zed", x=0.50, y=0.26, word_index=3),
        _word("a", x=0.20, y=0.263, word_index=1),
        _word("Mid", x=0.35, y=0.259, word_index=None),
    ]
    assert reconstruct_ocr_lines(elements) == ["a Mid Zed"]
