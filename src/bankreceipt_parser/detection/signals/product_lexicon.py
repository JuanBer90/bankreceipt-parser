"""Deterministic issuer/product text signal primitives (legacy heuristics)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bankreceipt_parser.detection.privacy import redact_sensitive_text
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.layout import (
    VerticalRegion,
    build_layout_profile,
    vertical_region_for_y,
)
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.lines import normalize_label

ISSUER_PRODUCT_SIGNALS: dict[Issuer, tuple[str, ...]] = {
    Issuer.UENO: ("ueno", "uenó", "uenó bank", "ueno bank"),
    Issuer.ITAU: ("itaú", "itau", "itau paraguay"),
    Issuer.CONTINENTAL: ("continental", "banco continental"),
    Issuer.FAMILIAR: ("familiar", "banco familiar"),
    Issuer.GNB: ("gnb", "grupo nación"),
    Issuer.BNF: ("bnf", "banco nacional de fomento"),
    Issuer.ATLAS: ("atlas", "banco atlas"),
    Issuer.MANGO: ("mango", "mango pay", "mango wallet"),
    Issuer.EKO: ("eko", "eko wallet"),
    Issuer.VAQUITA: ("vaquita",),
    Issuer.ZETA: ("zeta", "zetabanco"),
    Issuer.BANCOP: ("bancop",),
    Issuer.BASA: ("basa",),
    Issuer.SUDAMERIS: ("sudameris",),
    Issuer.COMECIPAR: ("comecipar", "coomecipar"),
    Issuer.ECLUB: ("eclub",),
    Issuer.INTERFISA: ("interfisa",),
    Issuer.FINANCIERA_PYJ: ("financiera pyj", "pyj"),
    Issuer.MEDALLA_MILAGROSA: ("medalla milagrosa",),
}

CONTEXT_ONLY_SIGNALS: tuple[str, ...] = (
    "sip",
    "spi",
    "transferencia",
    "comprobante",
    "destinatario",
    "remitente",
    "beneficiario",
    "concepto",
    "fecha",
    "monto",
    "operación",
    "operacion",
)

# Optional legal-entity tokens that may appear between OCR-split brand words.
_BRAND_WORD_GAP = r"(?:\s+(?:s\.?\s*a\.?|sa))?"

GENERIC_TRANSFER_PHRASES: tuple[str, ...] = (
    "comprobante de transferencia",
    "transferencia realizada",
    "comprobante",
)


@dataclass(frozen=True)
class SignalHit:
    """One matched issuer/product signal."""

    issuer_key: str
    matched_term: str
    region: VerticalRegion | None
    score: float


@dataclass(frozen=True)
class IssuerSignalSummary:
    """Privacy-safe summary of text/layout signals for one receipt."""

    top_hits: tuple[SignalHit, ...]
    generic_phrases: tuple[str, ...]
    context_terms: tuple[str, ...]
    layout_region_sequence: tuple[str, ...]
    header_tokens: tuple[str, ...]


def _eko_send_receipt_text(full_text: str) -> bool:
    """EKO send confirmation layout (counterparty bank text is not the receipt issuer)."""
    return (
        "listo" in full_text
        and "envio" in full_text
        and "compartir" in full_text
        and "comprobante" in full_text
    )


def score_text_signals(ocr: OCRResult) -> list[SignalHit]:
    """Score issuer/product signals from OCR text and header placement."""
    hits: list[SignalHit] = []
    full_text = normalize_label(ocr.text)
    seen_term: set[tuple[str, str]] = set()
    for issuer, terms in ISSUER_PRODUCT_SIGNALS.items():
        issuer_slug = issuer.value
        if issuer == Issuer.FAMILIAR and _eko_send_receipt_text(full_text):
            continue
        for term in terms:
            term_norm = normalize_label(term)
            dedupe_key = (issuer_slug, term_norm)
            if dedupe_key in seen_term:
                continue
            if not _normalized_term_matches_text(term_norm, full_text):
                continue
            seen_term.add(dedupe_key)
            region = _best_region_for_term(ocr, term_norm)
            base = 1.0
            if region in {VerticalRegion.HEADER, VerticalRegion.UPPER}:
                base += 0.5
            if region == VerticalRegion.FOOTER:
                base -= 0.2
            hits.append(
                SignalHit(
                    issuer_key=issuer_slug,
                    matched_term=term,
                    region=region,
                    score=base,
                )
            )
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits


def summarize_signals(ocr: OCRResult) -> IssuerSignalSummary:
    """Build a redacted, privacy-safe signal summary."""
    hits = score_text_signals(ocr)
    layout = build_layout_profile(ocr)
    generic = tuple(
        redact_sensitive_text(phrase)
        for phrase in GENERIC_TRANSFER_PHRASES
        if phrase.casefold() in ocr.text.casefold()
    )
    context = tuple(
        term
        for term in CONTEXT_ONLY_SIGNALS
        if re.search(rf"\b{re.escape(term)}\b", ocr.text, flags=re.I)
    )
    header_tokens = tuple(redact_sensitive_text(token) for token in layout.top_label_tokens)
    return IssuerSignalSummary(
        top_hits=tuple(hits[:5]),
        generic_phrases=generic,
        context_terms=context,
        layout_region_sequence=tuple(r.value for r in layout.region_sequence),
        header_tokens=header_tokens,
    )


def _normalized_term_matches_text(term_norm: str, full_text: str) -> bool:
    """Match issuer/product terms in normalized OCR, allowing split brand tokens."""
    words = term_norm.split()
    if len(words) == 1:
        pattern = r"(?<!\w)" + re.escape(term_norm) + r"(?!\w)"
        return re.search(pattern, full_text) is not None
    chunks: list[str] = []
    for index, word in enumerate(words):
        chunks.append(re.escape(word))
        if index < len(words) - 1:
            chunks.append(_BRAND_WORD_GAP + r"\s+")
    pattern = r"(?<!\w)" + "".join(chunks) + r"(?!\w)"
    return re.search(pattern, full_text) is not None


def _best_region_for_term(ocr: OCRResult, term_norm: str) -> VerticalRegion | None:
    for element in ocr.elements:
        element_text = normalize_label(element.text)
        if _normalized_term_matches_text(term_norm, element_text):
            return vertical_region_for_y(element.bbox.y)
    full_text = normalize_label(ocr.text)
    if not _normalized_term_matches_text(term_norm, full_text):
        return None
    anchor = term_norm.split()[0]
    for element in ocr.elements:
        element_text = normalize_label(element.text)
        if _normalized_term_matches_text(anchor, element_text):
            return vertical_region_for_y(element.bbox.y)
    return None
