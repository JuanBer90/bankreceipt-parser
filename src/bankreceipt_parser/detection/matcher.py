"""Evaluate issuer profiles and select the best match."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bankreceipt_parser.detection.profile import IssuerProfile, ProfileMatchResult

if TYPE_CHECKING:
    from PIL import Image

    from bankreceipt_parser.ocr.structure import OCRResult

PROFILE_MIN_MARGIN = 0.5


def evaluate_profiles(
    ocr: OCRResult,
    image: Image.Image | None,
    profiles: tuple[IssuerProfile, ...],
) -> list[ProfileMatchResult]:
    """Evaluate every profile independently."""
    return [profile.evaluate(ocr, image) for profile in profiles]


def best_profile_match(
    results: list[ProfileMatchResult],
    *,
    min_margin: float = PROFILE_MIN_MARGIN,
) -> ProfileMatchResult | None:
    """
    Return the top accepted profile when it clears ``min_score`` and beats the runner-up.

    Returns ``None`` when evidence is insufficient or ambiguous.
    """
    accepted = [r for r in results if r.accepted]
    if not accepted:
        return None
    ranked = sorted(accepted, key=lambda r: r.score, reverse=True)
    top = ranked[0]
    second = ranked[1].score if len(ranked) > 1 else 0.0
    if top.score - second < min_margin and len(ranked) > 1:
        return None
    return top
