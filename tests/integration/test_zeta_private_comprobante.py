"""Optional validation against the gitignored ``comprobantes/`` dataset (not run in CI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bankreceipt_parser import parse
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.tesseract import is_tesseract_installed

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ZETA_SAMPLE = REPOSITORY_ROOT / "comprobantes" / "ZETA" / "zeta.png"

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not is_tesseract_installed(), reason="Tesseract not installed")
@pytest.mark.skipif(not ZETA_SAMPLE.is_file(), reason="Private comprobantes/ZETA/zeta.png missing")
def test_private_zeta_sample_parses_with_live_tesseract() -> None:
    """
    Manual smoke test on a real receipt image kept outside the repository.

    Asserts only issuer and that core fields parsed; no golden values from the
    private image are embedded in this file.
    """
    result = parse(ZETA_SAMPLE)
    assert result.receipt is not None
    assert result.receipt.issuer == Issuer.ZETA
    assert result.receipt.amount is not None
    assert result.receipt.currency == "PYG"
    assert result.receipt.sender is not None
    assert result.receipt.sender.name
