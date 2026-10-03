"""Typed issuer/format profiles built from reusable signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.order import VerticalOrderSignal
from bankreceipt_parser.detection.signals.text import TextAbsenceSignal, TextSignal
from bankreceipt_parser.detection.signals.visual import BrandBlockSignal, BrandDensitySignal

if TYPE_CHECKING:
    from PIL import Image

    from bankreceipt_parser.ocr.structure import OCRResult

ProfileSignal = (
    TextSignal
    | ColorRegionSignal
    | TextAbsenceSignal
    | BrandBlockSignal
    | BrandDensitySignal
    | VerticalOrderSignal
)


@dataclass(frozen=True)
class SignalEvidence:
    """Outcome of evaluating one profile signal."""

    signal_id: str
    matched: bool
    score: float
    detail: str = ""


@dataclass(frozen=True)
class ProfileMatchResult:
    """Aggregated profile evaluation (score is not a probability)."""

    issuer: str
    variant: str
    score: float
    min_score: float
    matched_signals: tuple[str, ...]
    unmatched_signals: tuple[str, ...]
    evidence: tuple[SignalEvidence, ...]
    required_signals_missing: tuple[str, ...] = ()
    vetoed: bool = False

    @property
    def accepted(self) -> bool:
        return (
            not self.vetoed
            and not self.required_signals_missing
            and self.score >= self.min_score
        )


@dataclass(frozen=True)
class IssuerProfile:
    """
    Format variant fingerprint for a known issuer.

    Issuer identity is resolved separately from normalized brand/product text;
    ``signals`` here describe receipt layout/copy for variant matching only.
    """

    issuer: str
    variant: str
    signals: tuple[ProfileSignal, ...]
    exclusions: tuple[TextAbsenceSignal, ...] = ()
    required_signals: tuple[str, ...] = ()
    min_score: float = 3.0
    establish_issuer: bool = True
    issuer_only: bool = False

    def __post_init__(self) -> None:
        signal_ids = tuple(signal.signal_id for signal in self.signals)
        if len(set(signal_ids)) != len(signal_ids):
            raise ValueError("Profile signal identifiers must be unique.")
        unknown_required = set(self.required_signals) - set(signal_ids)
        if unknown_required:
            raise ValueError(
                "Required profile signals must be declared in signals: "
                f"{', '.join(sorted(unknown_required))}."
            )

    def evaluate(
        self,
        ocr: OCRResult,
        image: Image.Image | None,
    ) -> ProfileMatchResult:
        evidence: list[SignalEvidence] = []
        matched_ids: list[str] = []
        unmatched_ids: list[str] = []
        total = 0.0

        for exclusion in self.exclusions:
            triggered, _ = exclusion.evaluate(ocr)
            if triggered:
                return ProfileMatchResult(
                    issuer=self.issuer,
                    variant=self.variant,
                    score=0.0,
                    min_score=self.min_score,
                    matched_signals=(),
                    unmatched_signals=(exclusion.signal_id,),
                    evidence=(
                        SignalEvidence(
                            signal_id=exclusion.signal_id,
                            matched=True,
                            score=0.0,
                            detail="exclusion triggered",
                        ),
                    ),
                    required_signals_missing=(),
                    vetoed=True,
                )

        for signal in self.signals:
            if isinstance(signal, (ColorRegionSignal, BrandBlockSignal, BrandDensitySignal)):
                ok, points = signal.evaluate(image)
            else:
                ok, points = signal.evaluate(ocr)
            evidence.append(
                SignalEvidence(
                    signal_id=signal.signal_id,
                    matched=ok,
                    score=points,
                )
            )
            if ok:
                matched_ids.append(signal.signal_id)
                total += points
            else:
                unmatched_ids.append(signal.signal_id)

        return ProfileMatchResult(
            issuer=self.issuer,
            variant=self.variant,
            score=total,
            min_score=self.min_score,
            matched_signals=tuple(matched_ids),
            unmatched_signals=tuple(unmatched_ids),
            evidence=tuple(evidence),
            required_signals_missing=tuple(
                signal_id for signal_id in self.required_signals if signal_id not in matched_ids
            ),
        )
