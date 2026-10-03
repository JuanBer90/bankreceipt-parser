"""Tests for supplemental OCR merge (PSM 6 + gap-fill pass)."""

from __future__ import annotations

from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.ocr.supplemental_merge import merge_supplemental_tesseract_pass


def _line(text: str, y: float, height: float = 0.02) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        confidence=90.0,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.8, height=height),
        line_index=1,
        block_index=1,
        paragraph_index=1,
        level="line",
    )


def _word(text: str, x: float, y: float, conf: float = 85.0) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        confidence=conf,
        bbox=NormalizedBoundingBox(x=x, y=y, width=0.1, height=0.02),
        level="word",
    )


def _primary_result(*lines: OCRTextElement) -> OCRResult:
    return OCRResult(
        text="\n".join(line.text for line in lines),
        elements=list(lines),
        image_width=1000,
        image_height=1000,
    )


def _supplemental_dict(*words: OCRTextElement) -> dict[str, list[object]]:
    """Minimal Tesseract data dict with word-level entries only."""
    data: dict[str, list[object]] = {
        "level": [],
        "text": [],
        "conf": [],
        "left": [],
        "top": [],
        "width": [],
        "height": [],
        "line_num": [],
        "block_num": [],
        "par_num": [],
        "word_num": [],
    }
    for index, word in enumerate(words, start=1):
        data["level"].append(5)
        data["text"].append(word.text)
        data["conf"].append(word.confidence or 0)
        data["left"].append(int(word.bbox.x * 1000))
        data["top"].append(int(word.bbox.y * 1000))
        data["width"].append(int(word.bbox.width * 1000))
        data["height"].append(int(word.bbox.height * 1000))
        data["line_num"].append(1)
        data["block_num"].append(1)
        data["par_num"].append(1)
        data["word_num"].append(index)
    return data


def test_adds_words_only_in_vertical_gap() -> None:
    primary = _primary_result(_line("HEADER ONE", 0.10), _line("HEADER TWO", 0.40))
    supplemental = _supplemental_dict(
        _word("OMITTED", 0.35, 0.22),
        _word("TOKEN", 0.50, 0.22),
    )
    merged = merge_supplemental_tesseract_pass(primary, supplemental)
    assert "OMITTED TOKEN" in merged.text
    assert merged.text.index("HEADER ONE") < merged.text.index("OMITTED TOKEN")
    assert merged.text.index("OMITTED TOKEN") < merged.text.index("HEADER TWO")


def test_skips_duplicate_overlapping_text() -> None:
    primary = _primary_result(_line("KNOWN VALUE", 0.10), _line("FOOTER", 0.40))
    supplemental = _supplemental_dict(_word("KNOWN", 0.12, 0.10), _word("VALUE", 0.25, 0.10))
    merged = merge_supplemental_tesseract_pass(primary, supplemental)
    assert merged.text == primary.text
    assert len(merged.elements) == len(primary.elements)


def test_skips_low_confidence_words() -> None:
    primary = _primary_result(_line("TOP", 0.10), _line("BOTTOM", 0.40))
    supplemental = _supplemental_dict(_word("NOISE", 0.35, 0.22, conf=40.0))
    merged = merge_supplemental_tesseract_pass(primary, supplemental)
    assert merged.text == primary.text


def test_no_change_when_supplemental_empty() -> None:
    primary = _primary_result(_line("ONLY", 0.20))
    merged = merge_supplemental_tesseract_pass(primary, {"text": []})
    assert merged.text == primary.text


def test_reading_order_after_merge() -> None:
    primary = _primary_result(_line("ALPHA", 0.05), _line("OMEGA", 0.50))
    supplemental = _supplemental_dict(_word("BETA", 0.20, 0.25), _word("GAMMA", 0.35, 0.25))
    merged = merge_supplemental_tesseract_pass(primary, supplemental)
    lines = [line for line in merged.text.splitlines() if line.strip()]
    assert lines == ["ALPHA", "BETA GAMMA", "OMEGA"]


def test_gap_fill_recovers_display_amount_not_in_primary() -> None:
    """Regression: primary block OCR skips a centered amount; supplemental words fill the gap."""
    primary = _primary_result(
        _line("COMPROBANTE TRANSFERENCIA EJEMPLO", 0.08, height=0.05),
        _line("CONCEPTO PAGO EJEMPLO", 0.52, height=0.05),
    )
    assert "88.500" not in primary.text
    supplemental = _supplemental_dict(
        _word("Gs.", 0.20, 0.28),
        _word("88.500", 0.32, 0.28),
    )
    merged = merge_supplemental_tesseract_pass(primary, supplemental)
    assert "88.500" in merged.text
    assert "Gs. 88.500" in merged.text
    lines = [line for line in merged.text.splitlines() if line.strip()]
    assert lines == [
        "COMPROBANTE TRANSFERENCIA EJEMPLO",
        "Gs. 88.500",
        "CONCEPTO PAGO EJEMPLO",
    ]
