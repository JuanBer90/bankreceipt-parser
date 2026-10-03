"""Resolve receipt issuer from OCR text (independent of format variant)."""

from __future__ import annotations

from dataclasses import dataclass

from bankreceipt_parser.detection.outcome import (
    DetectionStatus,
    IssuerCandidate,
    IssuerDetectionOutcome,
)
from bankreceipt_parser.detection.signals.product_lexicon import SignalHit, score_text_signals
from bankreceipt_parser.ocr.layout import build_layout_profile
from bankreceipt_parser.ocr.structure import OCRResult

MIN_ISSUER_SCORE = 1.2
MIN_ISSUER_MARGIN = 0.25


@dataclass(frozen=True)
class IssuerResolution:
    """Strong enough issuer identification to skip variant-only UNKNOWN paths."""

    issuer: str
    score: float
    hits: tuple[SignalHit, ...]
    candidates: tuple[IssuerCandidate, ...]
    notes: tuple[str, ...]


def resolve_issuer(ocr: OCRResult) -> IssuerResolution | None:
    """
    Answer "who issued this receipt?" using normalized product/brand text only.

    Does not use color or layout fingerprints beyond header-weighted term placement.
    """
    outcome = _issuer_outcome_from_text_signals(ocr)
    if outcome.status != DetectionStatus.IDENTIFIED or outcome.issuer is None:
        return None
    hits = score_text_signals(ocr)
    return IssuerResolution(
        issuer=outcome.issuer,
        score=outcome.score or 0.0,
        hits=tuple(hits),
        candidates=tuple(outcome.candidates),
        notes=outcome.notes,
    )


def _issuer_outcome_from_text_signals(ocr: OCRResult) -> IssuerDetectionOutcome:
    """Legacy aggregation logic scoped to issuer identity (no variant profiles)."""
    from collections import defaultdict

    hits = score_text_signals(ocr)
    if not hits:
        return IssuerDetectionOutcome(
            status=DetectionStatus.UNKNOWN,
            notes=("No issuer/product text signals matched.",),
        )

    aggregated: dict[str, float] = defaultdict(float)
    methods: dict[str, set[str]] = defaultdict(set)
    for hit in hits:
        # Multiple lexicon aliases can describe the same bank mentioned as a
        # sender or recipient. They are corroborating spellings, not fully
        # independent issuer evidence: keep a small bonus for OCR forms such
        # as a brand plus its legal suffix, but do not let aliases outweigh a
        # strong header-localized issuer mark from another candidate.
        if aggregated[hit.issuer_key] == 0.0:
            aggregated[hit.issuer_key] = hit.score
        else:
            aggregated[hit.issuer_key] += min(hit.score, 0.2)
        methods[hit.issuer_key].add("text")

    ranked = sorted(aggregated.items(), key=lambda item: item[1], reverse=True)
    candidates = [
        IssuerCandidate(issuer=key, score=score, method="+".join(sorted(methods[key])))
        for key, score in ranked[:5]
    ]

    top_key, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top_score - second_score

    layout = build_layout_profile(ocr)
    notes: list[str] = []
    if len({hit.issuer_key for hit in hits[:3]}) > 1:
        notes.append("Multiple issuer/product signals present; possible ambiguity.")
    if margin < MIN_ISSUER_MARGIN:
        notes.append("Top candidates are too close; treating as ambiguous.")

    if top_score < MIN_ISSUER_SCORE or margin < MIN_ISSUER_MARGIN:
        return IssuerDetectionOutcome(
            status=DetectionStatus.UNKNOWN,
            score=top_score,
            method="text",
            candidates=candidates,
            notes=tuple(notes) or ("Insufficient separation between candidates.",),
        )

    notes.append(
        f"Layout sequence observed: {' > '.join(layout.region_sequence) or 'n/a'}"
    )
    return IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=top_key,
        score=top_score,
        method="text",
        candidates=candidates,
        notes=tuple(notes),
    )
