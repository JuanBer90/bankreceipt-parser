"""Minimal deterministic issuer/format detection heuristics."""

from __future__ import annotations

from PIL import Image

from bankreceipt_parser.detection.issuer_resolution import IssuerResolution, resolve_issuer
from bankreceipt_parser.detection.matcher import best_profile_match, evaluate_profiles
from bankreceipt_parser.detection.outcome import (
    DetectionStatus,
    IssuerCandidate,
    IssuerDetectionOutcome,
)
from bankreceipt_parser.detection.profile import IssuerProfile, ProfileMatchResult
from bankreceipt_parser.detection.profiles import ALL_PROFILES
from bankreceipt_parser.ocr.images import ImageSource, load_image, normalize_image_orientation
from bankreceipt_parser.ocr.structure import OCRResult

VARIANT_MIN_MARGIN = 0.25
ISSUER_PROFILE_MIN_MARGIN = 0.25


def detect_issuer_from_ocr(
    ocr: OCRResult,
    *,
    image: ImageSource | Image.Image | None = None,
) -> IssuerDetectionOutcome:
    """
    Detect issuer (brand/product text) then format variant (typed profiles).

    Strong normalized issuer text is enough for ``issuer``; variant profiles add
    layout/color only when needed (e.g. transfer summary without ``ueno`` in OCR).
    """
    pil = _resolve_image(image)
    profile_results = evaluate_profiles(ocr, pil, ALL_PROFILES)

    issuer_resolution = resolve_issuer(ocr)
    if issuer_resolution is None:
        issuer_resolution = _resolve_issuer_from_profiles(profile_results)

    if issuer_resolution is not None:
        variant_candidates = [
            r
            for r in profile_results
            if r.issuer == issuer_resolution.issuer
            and not _profile_issuer_only(r.issuer, r.variant)
        ]
        variant_match = best_profile_match(variant_candidates, min_margin=VARIANT_MIN_MARGIN)
        if variant_match is not None and variant_match.accepted:
            return _outcome_from_profile(
                variant_match,
                profile_results,
                issuer_resolution=issuer_resolution,
            )
        return _outcome_issuer_only(issuer_resolution)

    self_establishing = [
        r
        for r in profile_results
        if _profile_establish_issuer(r.issuer, r.variant)
        and not _profile_issuer_only(r.issuer, r.variant)
    ]
    profile_best = best_profile_match(self_establishing)
    if profile_best is not None:
        return _outcome_from_profile(profile_best, profile_results, issuer_resolution=None)

    return IssuerDetectionOutcome(
        status=DetectionStatus.UNKNOWN,
        notes=("No issuer text or format profile matched.",),
    )


def _resolve_issuer_from_profiles(
    profile_results: list[ProfileMatchResult],
) -> IssuerResolution | None:
    issuer_profiles = [
        r
        for r in profile_results
        if _profile_issuer_only(r.issuer, r.variant) and r.accepted
    ]
    best = best_profile_match(issuer_profiles, min_margin=ISSUER_PROFILE_MIN_MARGIN)
    if best is None:
        return None
    method = "visual" if _profile_uses_visual(best.issuer, best.variant) else "text"
    return IssuerResolution(
        issuer=best.issuer,
        score=best.score,
        hits=(),
        candidates=(
            IssuerCandidate(issuer=best.issuer, score=best.score, method=method),
        ),
        notes=(
            f"Issuer established from profile {best.variant} "
            f"(score={best.score:.2f}, signals={', '.join(best.matched_signals)}).",
        ),
    )


def _outcome_issuer_only(resolution: IssuerResolution) -> IssuerDetectionOutcome:
    method = resolution.candidates[0].method if resolution.candidates else "text"
    return IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=resolution.issuer,
        score=resolution.score,
        method=method,
        candidates=list(resolution.candidates),
        notes=resolution.notes,
    )


def _outcome_from_profile(
    match: ProfileMatchResult,
    all_results: list[ProfileMatchResult],
    *,
    issuer_resolution: IssuerResolution | None,
) -> IssuerDetectionOutcome:
    candidates = [
        IssuerCandidate(
            issuer=f"{r.issuer}:{r.variant}",
            score=r.score,
            method="profile",
        )
        for r in sorted(all_results, key=lambda item: item.score, reverse=True)
        if r.score > 0 and not r.vetoed and not _profile_issuer_only(r.issuer, r.variant)
    ][:5]

    notes: list[str] = []
    if issuer_resolution is not None:
        notes.extend(issuer_resolution.notes)
    else:
        notes.append("Issuer established from format profile (no brand text match).")

    notes.append(
        f"Variant profile: {match.variant} "
        f"(score={match.score:.2f}, signals={', '.join(match.matched_signals)})."
    )

    issuer_score = match.score
    method = "profile"
    if issuer_resolution is not None:
        issuer_score = max(issuer_resolution.score, match.score)
        res_method = resolution_method(issuer_resolution)
        method = f"{res_method}+profile" if res_method != "profile" else "text+profile"

    if not candidates and issuer_resolution is not None:
        candidates = list(issuer_resolution.candidates)

    return IssuerDetectionOutcome(
        status=DetectionStatus.IDENTIFIED,
        issuer=match.issuer,
        variant=match.variant,
        score=issuer_score,
        method=method,
        candidates=candidates,
        matched_signals=match.matched_signals,
        unmatched_signals=match.unmatched_signals,
        notes=tuple(notes),
    )


def resolution_method(resolution: IssuerResolution) -> str:
    if resolution.candidates:
        return resolution.candidates[0].method
    return "text"


def _profile_lookup(issuer: str, variant: str) -> IssuerProfile | None:
    for profile in ALL_PROFILES:
        if profile.issuer == issuer and profile.variant == variant:
            return profile
    return None


def _profile_establish_issuer(issuer: str, variant: str) -> bool:
    profile = _profile_lookup(issuer, variant)
    if profile is None:
        return True
    return profile.establish_issuer


def _profile_issuer_only(issuer: str, variant: str) -> bool:
    profile = _profile_lookup(issuer, variant)
    if profile is None:
        return False
    return profile.issuer_only


def _profile_uses_visual(issuer: str, variant: str) -> bool:
    profile = _profile_lookup(issuer, variant)
    if profile is None:
        return False
    from bankreceipt_parser.detection.signals.visual import BrandBlockSignal, BrandDensitySignal

    visual_types = (BrandBlockSignal, BrandDensitySignal)
    return any(isinstance(signal, visual_types) for signal in profile.signals)


def _resolve_image(image: ImageSource | Image.Image | None) -> Image.Image | None:
    if image is None:
        return None
    if isinstance(image, Image.Image):
        return image
    loaded, _ = load_image(image)
    return normalize_image_orientation(loaded)
