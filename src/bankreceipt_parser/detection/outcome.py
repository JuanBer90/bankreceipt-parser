"""Issuer and receipt-format detection outcomes."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DetectionStatus(StrEnum):
    """Whether issuer/format identification succeeded (independent of parsing)."""

    UNKNOWN = "unknown"
    IDENTIFIED = "identified"


class IssuerCandidate(BaseModel):
    """Heuristic issuer/format candidate (score is not a calibrated probability)."""

    issuer: str
    score: float = Field(ge=0.0)
    method: str = Field(description="text, layout, or visual")


class IssuerDetectionOutcome(BaseModel):
    """Result of deterministic issuer/format detection."""

    status: DetectionStatus = DetectionStatus.UNKNOWN
    issuer: str | None = None
    variant: str | None = None
    score: float | None = None
    method: str | None = None
    candidates: list[IssuerCandidate] = Field(default_factory=list)
    matched_signals: tuple[str, ...] = ()
    unmatched_signals: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
