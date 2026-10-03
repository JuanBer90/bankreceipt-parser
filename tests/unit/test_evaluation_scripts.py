"""Privacy defaults for local evaluation scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from bankreceipt_parser.ocr.health import DatasetOCRHealthReport, ImageOCRHealth, OCRHealthStatus


def _load_evaluate_ocr_module() -> object:
    script = Path(__file__).parents[2] / "scripts" / "evaluate_ocr.py"
    spec = importlib.util.spec_from_file_location("evaluate_ocr_script", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ocr_evaluation_hides_paths_without_verbose_mode() -> None:
    module = _load_evaluate_ocr_module()
    report = DatasetOCRHealthReport(
        root=Path("/private/receipts"),
        images_discovered=1,
        images_loaded=1,
        results=[
            ImageOCRHealth(
                relative_path="sensitive-folder/receipt.png",
                dataset_label="sensitive-folder",
                status=OCRHealthStatus.SUCCESS,
            )
        ],
    )

    output = module._format_report(report)

    assert "sensitive-folder" not in output
    assert "/private/receipts" not in output
