"""Synthetic Tesseract payloads for supplemental OCR merge regression tests."""

from __future__ import annotations


def tesseract_line_dict(
    entries: tuple[tuple[str, int, int, int, int], ...],
    *,
    image_width: int = 1000,
    image_height: int = 1000,
) -> dict[str, list[object]]:
    """Build a minimal Tesseract ``image_to_data`` dict with level-4 lines."""
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
    for line_index, (text, left, top, width, height) in enumerate(entries, start=1):
        data["level"].append(4)
        data["text"].append(text)
        data["conf"].append(90)
        data["left"].append(left)
        data["top"].append(top)
        data["width"].append(width)
        data["height"].append(height)
        data["line_num"].append(line_index)
        data["block_num"].append(1)
        data["par_num"].append(1)
        data["word_num"].append(0)
    _ = image_width, image_height
    return data


def tesseract_word_dict(
    entries: tuple[tuple[str, int, int, int, int, float], ...],
) -> dict[str, list[object]]:
    """Build a minimal Tesseract dict with level-5 words (text, left, top, w, h, conf)."""
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
    for word_index, (text, left, top, width, height, conf) in enumerate(entries, start=1):
        data["level"].append(5)
        data["text"].append(text)
        data["conf"].append(conf)
        data["left"].append(left)
        data["top"].append(top)
        data["width"].append(width)
        data["height"].append(height)
        data["line_num"].append(1)
        data["block_num"].append(1)
        data["par_num"].append(1)
        data["word_num"].append(word_index)
    return data


def fictional_primary_without_centered_amount() -> dict[str, list[object]]:
    """PSM-6-like lines: header and footer blocks with a vertical gap (no amount line)."""
    return tesseract_line_dict(
        (
            ("COMPROBANTE TRANSFERENCIA EJEMPLO", 80, 80, 840, 48),
            ("CONCEPTO PAGO EJEMPLO", 80, 520, 640, 48),
        ),
    )


def fictional_supplemental_amount_in_gap() -> dict[str, list[object]]:
    """PSM-3-like words for a display amount sitting in the primary vertical gap."""
    return tesseract_word_dict(
        (
            ("Gs.", 200, 280, 60, 36, 92.0),
            ("88.500", 280, 278, 140, 40, 91.0),
        ),
    )

