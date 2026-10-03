"""Privacy-safe OCR health metrics for local dataset evaluation (no ground-truth accuracy)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from time import perf_counter

from bankreceipt_parser.exceptions import (
    BankReceiptParserError,
    ImageLoadError,
    UnsupportedImageError,
)
from bankreceipt_parser.ocr.engine import OCREngine
from bankreceipt_parser.ocr.images import load_image
from bankreceipt_parser.ocr.pipeline import extract_text_with_details
from bankreceipt_parser.ocr.preprocessing import PreprocessOptions

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})


class OCRHealthStatus(StrEnum):
    """Heuristic OCR yield categories (not semantic accuracy)."""

    SUCCESS = "success"
    MARGINAL = "marginal"
    POOR = "poor"
    FAILED = "failed"
    LOAD_FAILED = "load_failed"


@dataclass(frozen=True)
class OCRHealthThresholds:
    """Tune heuristics for 'useful raw text' without labeled transcriptions."""

    poor_max_characters: int = 120
    poor_max_non_empty_lines: int = 5
    success_min_characters: int = 200
    success_min_non_empty_lines: int = 8


@dataclass(frozen=True)
class ImageOCRHealth:
    """Privacy-safe per-image OCR outcome."""

    relative_path: str
    dataset_label: str
    status: OCRHealthStatus
    non_empty_lines: int = 0
    characters: int = 0
    seconds: float = 0.0
    reason: str | None = None


@dataclass
class DirectoryOCRHealth:
    """Aggregate counts for one top-level dataset folder."""

    label: str
    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)


@dataclass
class DatasetOCRHealthReport:
    """Aggregate OCR health for an on-disk image tree."""

    root: Path
    images_discovered: int = 0
    images_loaded: int = 0
    results: list[ImageOCRHealth] = field(default_factory=list)
    total_seconds: float = 0.0

    def directory_summaries(self) -> list[DirectoryOCRHealth]:
        buckets: dict[str, DirectoryOCRHealth] = {}
        for item in self.results:
            bucket = buckets.setdefault(
                item.dataset_label,
                DirectoryOCRHealth(label=item.dataset_label),
            )
            bucket.total += 1
            key = item.status.value
            bucket.by_status[key] = bucket.by_status.get(key, 0) + 1
        return sorted(buckets.values(), key=lambda d: d.label.lower())

    def status_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for item in self.results:
            key = item.status.value
            totals[key] = totals.get(key, 0) + 1
        return totals

    def average_characters(self) -> float:
        values = [r.characters for r in self.results if r.status != OCRHealthStatus.FAILED]
        return sum(values) / len(values) if values else 0.0

    def average_non_empty_lines(self) -> float:
        values = [r.non_empty_lines for r in self.results if r.status != OCRHealthStatus.FAILED]
        return sum(values) / len(values) if values else 0.0


def classify_ocr_yield(
    *,
    characters: int,
    non_empty_lines: int,
    thresholds: OCRHealthThresholds | None = None,
) -> OCRHealthStatus:
    """Classify OCR yield using volume heuristics only."""
    limits = thresholds or OCRHealthThresholds()
    if (
        characters <= limits.poor_max_characters
        or non_empty_lines <= limits.poor_max_non_empty_lines
    ):
        return OCRHealthStatus.POOR
    if (
        characters >= limits.success_min_characters
        and non_empty_lines >= limits.success_min_non_empty_lines
    ):
        return OCRHealthStatus.SUCCESS
    return OCRHealthStatus.MARGINAL


def discover_image_paths(root: Path) -> list[Path]:
    """List image files under root (does not follow symlinks outside root)."""
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            paths.append(path)
    return paths


def _dataset_label(root: Path, image_path: Path) -> str:
    rel = image_path.relative_to(root)
    if len(rel.parts) > 1:
        return rel.parts[0]
    return "(root)"


def evaluate_image_ocr_health(
    image_path: Path,
    *,
    root: Path,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
    thresholds: OCRHealthThresholds | None = None,
) -> ImageOCRHealth:
    """Run OCR on one image and return privacy-safe health metadata."""
    rel = str(image_path.relative_to(root))
    label = _dataset_label(root, image_path)
    started = perf_counter()
    try:
        load_image(image_path)
    except (ImageLoadError, UnsupportedImageError) as exc:
        return ImageOCRHealth(
            relative_path=rel,
            dataset_label=label,
            status=OCRHealthStatus.LOAD_FAILED,
            seconds=perf_counter() - started,
            reason=str(exc),
        )

    try:
        ocr_result = extract_text_with_details(
            image_path,
            ocr_engine=ocr_engine,
            preprocess_options=preprocess_options,
        )
    except BankReceiptParserError as exc:
        return ImageOCRHealth(
            relative_path=rel,
            dataset_label=label,
            status=OCRHealthStatus.FAILED,
            seconds=perf_counter() - started,
            reason=str(exc),
        )

    lines = len([line for line in ocr_result.text.split("\n") if line.strip()])
    chars = len(ocr_result.text)
    status = classify_ocr_yield(characters=chars, non_empty_lines=lines, thresholds=thresholds)
    reason = None
    if status == OCRHealthStatus.POOR:
        reason = "very little text detected"
    return ImageOCRHealth(
        relative_path=rel,
        dataset_label=label,
        status=status,
        non_empty_lines=lines,
        characters=chars,
        seconds=perf_counter() - started,
        reason=reason,
    )


def evaluate_dataset_ocr_health(
    root: Path,
    *,
    ocr_engine: OCREngine | None = None,
    preprocess_options: PreprocessOptions | None = None,
    thresholds: OCRHealthThresholds | None = None,
) -> DatasetOCRHealthReport:
    """Evaluate OCR health for every image under root without persisting OCR text."""
    started = perf_counter()
    paths = discover_image_paths(root)
    report = DatasetOCRHealthReport(root=root.resolve(), images_discovered=len(paths))
    for path in paths:
        try:
            load_image(path)
            report.images_loaded += 1
        except (ImageLoadError, UnsupportedImageError):
            pass
        report.results.append(
            evaluate_image_ocr_health(
                path,
                root=root,
                ocr_engine=ocr_engine,
                preprocess_options=preprocess_options,
                thresholds=thresholds,
            )
        )
    report.total_seconds = perf_counter() - started
    return report
