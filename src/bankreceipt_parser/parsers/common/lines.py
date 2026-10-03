"""Build reading-order lines from structured OCR elements."""

from __future__ import annotations

import re
import unicodedata

from bankreceipt_parser.ocr.reading_order import reconstruct_ocr_lines
from bankreceipt_parser.ocr.structure import OCRResult


def normalize_label(text: str) -> str:
    """Casefold and strip accents for label matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.casefold()).strip()


def lines_from_ocr(ocr: OCRResult, *, y_tolerance: float = 0.018) -> list[str]:
    """Group OCR elements into horizontal lines in reading order."""
    if not ocr.elements:
        return [line for line in ocr.text.split("\n") if line.strip()]

    return reconstruct_ocr_lines(ocr.elements, y_tolerance=y_tolerance)


def find_line_index(lines: list[str], label_pattern: str) -> int | None:
    """Return index of first line whose normalized text contains the pattern."""
    target = normalize_label(label_pattern)
    for index, line in enumerate(lines):
        if target in normalize_label(line):
            return index
    return None


def find_exact_line(lines: list[str], label: str) -> int | None:
    """Return index of a line that equals the label after normalization."""
    target = normalize_label(label)
    for index, line in enumerate(lines):
        if normalize_label(line) == target:
            return index
    return None


def value_on_same_line(line: str, label_pattern: str) -> str | None:
    """Extract trailing value from a ``Label: value`` style line."""
    normalized = normalize_label(line)
    target = normalize_label(label_pattern)
    if target not in normalized:
        return None
    # Split on first colon if present
    if ":" in line:
        _, _, tail = line.partition(":")
        tail = tail.strip()
        return tail or None
    return None


def collect_name_block(lines: list[str], start_index: int, *, max_lines: int = 2) -> str | None:
    """Join subsequent lines that look like a person name block."""
    parts: list[str] = []
    for offset in range(max_lines):
        idx = start_index + offset
        if idx >= len(lines):
            break
        line = lines[idx].strip()
        norm = normalize_label(line)
        if not line or norm.startswith(("caja", "nro", "cuenta", "entidad", "moneda")):
            break
        if any(
            token in norm
            for token in ("comprobante", "transferencia", "operación", "operacion", "detalle")
        ):
            break
        parts.append(line)
    joined = " ".join(parts).strip()
    return joined or None
