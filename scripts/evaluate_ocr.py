#!/usr/bin/env python3
"""
Local development tool: evaluate OCR health on a private image directory.

Does not print OCR text and does not write extracted text to disk.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bankreceipt_parser.ocr.health import (
    DatasetOCRHealthReport,
    OCRHealthStatus,
    evaluate_dataset_ocr_health,
)
from bankreceipt_parser.ocr.tesseract import is_tesseract_installed


def _format_report(report: DatasetOCRHealthReport, *, verbose: bool = False) -> str:
    lines: list[str] = []
    lines.append(f"images_discovered: {report.images_discovered}")
    lines.append(f"images_loaded: {report.images_loaded}")
    lines.append(f"total_seconds: {report.total_seconds:.2f}")
    totals = report.status_totals()
    lines.append(f"status_totals: {totals}")
    lines.append(
        "averages (non-failed): "
        f"characters={report.average_characters():.1f} "
        f"non_empty_lines={report.average_non_empty_lines():.1f}"
    )
    if verbose:
        lines.append("")
        lines.append(f"root: {report.root}")
        lines.append("by_directory:")
        for summary in report.directory_summaries():
            lines.append(f"  {summary.label}: {summary.total} images {summary.by_status}")
        lines.append("")
        lines.append("per_image:")
        for item in report.results:
            reason = f" | reason: {item.reason}" if item.reason else ""
            lines.append(
                f"  {item.relative_path} | OCR: {item.status.value} | "
                f"non-empty lines: {item.non_empty_lines} | characters: {item.characters} | "
                f"seconds: {item.seconds:.2f}{reason}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate local OCR health on a directory of receipt images (dev only).",
    )
    parser.add_argument(
        "image_root",
        type=Path,
        help="Directory containing private receipt images (e.g. comprobantes/)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print paths and per-image details for local debugging.",
    )
    args = parser.parse_args(argv)

    root = args.image_root.expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    if not is_tesseract_installed():
        print(
            "warning: Tesseract is not installed; OCR evaluation will likely fail.",
            file=sys.stderr,
        )

    report = evaluate_dataset_ocr_health(root)
    print(_format_report(report, verbose=args.verbose))

    failed = report.status_totals().get(OCRHealthStatus.FAILED.value, 0)
    load_failed = report.status_totals().get(OCRHealthStatus.LOAD_FAILED.value, 0)
    return 1 if (failed or load_failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
