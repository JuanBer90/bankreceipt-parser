"""Optional live OCR test (skipped when Tesseract is unavailable)."""

from __future__ import annotations

import pytest

from bankreceipt_parser import extract_text
from bankreceipt_parser.ocr.tesseract import is_tesseract_installed
from helpers.synthetic_images import render_text_image

pytestmark = pytest.mark.skipif(
    not is_tesseract_installed(),
    reason="Tesseract executable is not installed",
)

SYNTHETIC_LINES = [
    "COMPROBANTE DE TRANSFERENCIA",
    "Monto: Gs. 50.000",
    "Fecha: 01/10/2026",
    "Operacion: TEST-12345",
]


def test_live_tesseract_reads_synthetic_receipt() -> None:
    image = render_text_image(SYNTHETIC_LINES, width=1000, height=700)
    text = extract_text(image)
    upper = text.upper()
    assert "TRANSFERENCIA" in upper
    assert "COMPROBANTE" in upper or "CCOMPROBANTE" in upper
    assert "TEST" in upper
    assert "GS" in upper or "MONTO" in upper or "MONTA" in upper
