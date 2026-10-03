"""Tests for the development receipt-parsing CLI."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from bankreceipt_parser.exceptions import ImageLoadError
from bankreceipt_parser.models.result import ParseResult


def _load_script_module() -> object:
    script = Path(__file__).parents[2] / "scripts" / "parse_receipt.py"
    spec = importlib.util.spec_from_file_location("parse_receipt_script", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_prints_public_parse_result_without_raw_ocr(capsys: object) -> None:
    module = _load_script_module()
    result = ParseResult(raw_ocr_text="synthetic private text", warnings=["no parser"])
    with patch.object(module, "parse", return_value=result) as parse:
        exit_code = module.main(["synthetic.png"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert parse.call_args.kwargs["include_raw_ocr"] is False
    assert "raw_ocr_text" not in output
    assert "synthetic private text" not in json.dumps(output)


def test_cli_debug_opt_in_includes_raw_ocr(capsys: object) -> None:
    module = _load_script_module()
    result = ParseResult(raw_ocr_text="synthetic debug text")
    with patch.object(module, "parse", return_value=result) as parse:
        exit_code = module.main(["--debug", "--no-pretty", "synthetic.png"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert parse.call_args.kwargs["include_raw_ocr"] is True
    assert output["debug"]["raw_ocr_text"] == "synthetic debug text"


def test_cli_reports_domain_errors_to_stderr(capsys: object) -> None:
    module = _load_script_module()
    with patch.object(module, "parse", side_effect=ImageLoadError("synthetic failure")):
        exit_code = module.main(["missing.png"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "synthetic failure" in captured.err
