"""Tests for privacy-safe OCR health metrics."""

from __future__ import annotations

from pathlib import Path

from bankreceipt_parser.ocr.health import (
    OCRHealthStatus,
    classify_ocr_yield,
    discover_image_paths,
    evaluate_dataset_ocr_health,
)
from helpers.synthetic_images import render_text_image


def test_classify_ocr_yield_success() -> None:
    assert classify_ocr_yield(characters=250, non_empty_lines=10) == OCRHealthStatus.SUCCESS


def test_classify_ocr_yield_poor() -> None:
    assert classify_ocr_yield(characters=50, non_empty_lines=2) == OCRHealthStatus.POOR


def test_classify_ocr_yield_marginal() -> None:
    assert classify_ocr_yield(characters=150, non_empty_lines=7) == OCRHealthStatus.MARGINAL


def test_discover_image_paths(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(render_text_image(["x"]))
    (tmp_path / "skip.txt").write_text("nope", encoding="utf-8")
    nested = tmp_path / "UENO"
    nested.mkdir()
    (nested / "b.jpg").write_bytes(render_text_image(["y"]))
    paths = discover_image_paths(tmp_path)
    assert len(paths) == 2


def test_evaluate_dataset_ocr_health_with_stub_engine(tmp_path: Path) -> None:
    png = tmp_path / "sample.png"
    png.write_bytes(render_text_image(["COMPROBANTE", "Linea dos"]))

    class _Stub:
        def extract_text(self, image: bytes) -> str:
            lines = [f"Linea inventada numero {i} con texto de relleno" for i in range(1, 12)]
            return "\n".join(lines)

    report = evaluate_dataset_ocr_health(tmp_path, ocr_engine=_Stub())
    assert report.images_discovered == 1
    assert report.results[0].status == OCRHealthStatus.SUCCESS
    assert report.results[0].characters > 0
    assert "COMPROBANTE" not in str(report.results[0])


def test_evaluate_dataset_missing_root(tmp_path: Path) -> None:
    report = evaluate_dataset_ocr_health(tmp_path / "missing")
    assert report.images_discovered == 0
    assert report.results == []
