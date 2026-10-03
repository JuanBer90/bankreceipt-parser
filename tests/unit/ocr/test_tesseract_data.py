"""Tests for Tesseract data parsing into structured OCR."""

from __future__ import annotations

from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.ocr.tesseract_data import build_ocr_result_from_tesseract_data


def test_build_ocr_result_normalizes_bounding_boxes() -> None:
    data = {
        "level": [4, 4],
        "page_num": [1, 1],
        "block_num": [1, 1],
        "par_num": [1, 1],
        "line_num": [1, 2],
        "word_num": [0, 0],
        "left": [100, 100],
        "top": [200, 300],
        "width": [400, 400],
        "height": [50, 50],
        "conf": [90, 88],
        "text": ["Comprobante", "Transferencia"],
    }
    result = build_ocr_result_from_tesseract_data(
        data=data,
        image_width=1000,
        image_height=2000,
    )
    assert result.text == "Comprobante\nTransferencia"
    assert len(result.elements) == 2
    first = result.elements[0]
    assert first.bbox.x == 0.1
    assert first.bbox.y == 0.1
    assert first.bbox.width == 0.4
    assert first.line_index == 1
    assert first.paragraph_index == 1
    assert first.word_index is None


def test_build_ocr_result_word_level_joins_structural_line() -> None:
    data = {
        "level": [5, 5],
        "page_num": [1, 1],
        "block_num": [1, 1],
        "par_num": [1, 1],
        "line_num": [2, 2],
        "word_num": [1, 2],
        "left": [168, 190],
        "top": [420, 415],
        "width": [11, 101],
        "height": [14, 19],
        "conf": [96, 96],
        "text": ["a", "Ejemplo"],
    }
    result = build_ocr_result_from_tesseract_data(
        data=data,
        image_width=1000,
        image_height=2000,
    )
    assert result.text == "a Ejemplo"
    assert [element.text for element in result.elements] == ["a", "Ejemplo"]
    assert result.elements[0].word_index == 1
    assert result.elements[1].word_index == 2


def test_extract_text_compatible_text_field() -> None:
    empty = OCRResult(text="hola", elements=[], image_width=10, image_height=10)
    assert empty.text == "hola"


def test_build_ocr_result_synthesizes_line_when_line_level_text_empty() -> None:
    data = {
        "level": [4, 5, 5],
        "page_num": [1, 1, 1],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 1],
        "word_num": [0, 1, 2],
        "left": [100, 100, 160],
        "top": [200, 200, 200],
        "width": [0, 40, 80],
        "height": [50, 20, 20],
        "conf": [-1, 90, 88],
        "text": ["", "Gs.", "88.000"],
    }
    result = build_ocr_result_from_tesseract_data(
        data=data,
        image_width=1000,
        image_height=2000,
    )
    assert result.text == "Gs. 88.000"
    assert len(result.elements) == 1
    assert result.elements[0].text == "Gs. 88.000"
    assert result.elements[0].level == "line"
