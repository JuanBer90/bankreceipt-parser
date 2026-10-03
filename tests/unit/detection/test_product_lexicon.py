"""Product lexicon consistency tests."""

from __future__ import annotations

from bankreceipt_parser.detection.signals.product_lexicon import (
    ISSUER_PRODUCT_SIGNALS,
    _normalized_term_matches_text,
    score_text_signals,
)
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.lines import normalize_label


def test_issuer_product_signals_covers_all_issuers() -> None:
    assert set(ISSUER_PRODUCT_SIGNALS) == set(Issuer)
    for issuer, terms in ISSUER_PRODUCT_SIGNALS.items():
        assert isinstance(issuer, Issuer)
        assert terms
        assert all(term.strip() for term in terms)


def test_bancop_signals_exclude_banco_do_brasil() -> None:
    terms = ISSUER_PRODUCT_SIGNALS[Issuer.BANCOP]
    assert "bancop" in terms
    assert not any("brasil" in term.casefold() for term in terms)


def _ocr(text: str) -> OCRResult:
    return OCRResult(text=text, elements=[], image_width=1, image_height=1)


def test_single_token_eko_matches_standalone_word() -> None:
    hits = score_text_signals(_ocr("transferencia desde eko wallet"))
    assert any(hit.issuer_key == Issuer.EKO.value for hit in hits)


def test_single_token_eko_does_not_match_inside_another_word() -> None:
    hits = score_text_signals(_ocr("comprobante dezekontrol"))
    assert not any(hit.issuer_key == Issuer.EKO.value for hit in hits)


def test_single_token_zeta_does_not_match_substring() -> None:
    hits = score_text_signals(_ocr("producto azetabank transferencia"))
    assert not any(hit.issuer_key == Issuer.ZETA.value for hit in hits)


def test_single_token_zeta_matches_when_delimited() -> None:
    hits = score_text_signals(_ocr("zeta banco comprobante"))
    assert any(hit.issuer_key == Issuer.ZETA.value for hit in hits)


def test_zetabonco_lexicon_term_matches_institutional_token() -> None:
    """OCR-glued brand variant is a whole token (word boundaries), not a zeta substring."""
    text = normalize_label("@ zetabonco comprobante")
    assert _normalized_term_matches_text("zeta", text) is False
    assert _normalized_term_matches_text("zetabonco", text) is True
    hits = score_text_signals(_ocr("@ zetabonco comprobante transferencia"))
    zeta_hits = [h for h in hits if h.issuer_key == Issuer.ZETA.value]
    assert any(h.matched_term == "zetabonco" for h in zeta_hits)
