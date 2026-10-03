#!/usr/bin/env python3
"""Developer tool: privacy-safe issuer/format signal research on a private image tree."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.signals import summarize_signals
from bankreceipt_parser.ocr.health import discover_image_paths
from bankreceipt_parser.ocr.pipeline import extract_ocr_with_details
from bankreceipt_parser.ocr.tesseract import is_tesseract_installed


def _dataset_label(root: Path, image_path: Path) -> str:
    rel = image_path.relative_to(root)
    if len(rel.parts) > 1:
        return rel.parts[0]
    return "(root)"


def _issuer_key_from_label(label: str) -> str | None:
    """Normalize a private dataset folder label for local aggregate evaluation only."""
    if label == "(root)":
        return None
    return re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_") or None


def _format_hits(summary: object) -> str:
    hits = getattr(summary, "top_hits", ())
    if not hits:
        return "-"
    return ", ".join(f"{hit.issuer_key}({hit.score:.1f})" for hit in hits[:3])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate issuer/format signals (dev only).")
    parser.add_argument(
        "image_root",
        type=Path,
        help="Private image directory (e.g. comprobantes/)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-image paths and dataset labels for local debugging.",
    )
    args = parser.parse_args(argv)

    root = args.image_root.expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    if not is_tesseract_installed():
        print("warning: Tesseract not installed.", file=sys.stderr)

    paths = discover_image_paths(root)
    matrix_rows: list[str] = []
    by_label: dict[str, list[str]] = defaultdict(list)
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in paths:
        rel = str(path.relative_to(root))
        label = _dataset_label(root, path)
        ocr = extract_ocr_with_details(path)
        summary = summarize_signals(ocr)
        outcome = detect_issuer_from_ocr(ocr, image=path)
        variant = outcome.variant or "-"
        if args.verbose:
            matrix_rows.append(
                f"{rel} | label={label} | elements={len(ocr.elements)} | "
                f"hits={_format_hits(summary)} | candidate={outcome.issuer or '-'} | "
                f"variant={variant} | status={outcome.status.value} | "
                f"score={outcome.score or 0:.2f} | method={outcome.method or '-'} | "
                f"layout={' > '.join(summary.layout_region_sequence)}"
            )
        by_label[label].append(outcome.status.value)
        expected_issuer = _issuer_key_from_label(label)
        if outcome.status.value == "unknown":
            matrix[label]["unknown"] += 1
        elif outcome.issuer == expected_issuer:
            matrix[label]["detected"] += 1
        else:
            matrix[label]["false_positive"] += 1

    print(f"images: {len(paths)}")
    totals: dict[str, int] = defaultdict(int)
    for label in sorted(by_label):
        row = matrix[label]
        detected = row["detected"]
        unknown = row["unknown"]
        false_positive = row["false_positive"]
        totals["detected"] += detected
        totals["unknown"] += unknown
        totals["false_positive"] += false_positive
    print(
        "TOTAL: "
        f"samples={len(paths)} | detected={totals['detected']} | "
        f"unknown={totals['unknown']} | false_positives={totals['false_positive']}"
    )
    if args.verbose:
        print("\nper_image:")
        for row in matrix_rows:
            print(f"  {row}")
        print("\nlabel_status_counts:")
        for label in sorted(by_label):
            counts: dict[str, int] = defaultdict(int)
            for status in by_label[label]:
                counts[status] += 1
            print(f"  {label}: {dict(counts)}")
        print("\nevaluation_matrix:")
        for label in sorted(by_label):
            row = matrix[label]
            print(
                f"  {label}: samples={len(by_label[label])} | detected={row['detected']} | "
                f"unknown={row['unknown']} | false_positives={row['false_positive']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
