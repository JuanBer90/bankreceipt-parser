#!/usr/bin/env python3
"""Parse one receipt through the public bankreceipt-parser API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Development scripts run directly from the repository root. Add the src-layout
# package location only when the project has not been installed into the active venv.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bankreceipt_parser import parse  # noqa: E402
from bankreceipt_parser.exceptions import BankReceiptParserError  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse a receipt image through the public bankreceipt-parser API.",
    )
    parser.add_argument("image_path", type=Path, help="PNG, JPEG, or WEBP receipt image.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include explicitly requested raw OCR and public-API diagnostic limitations.",
    )
    formatting = parser.add_mutually_exclusive_group()
    formatting.add_argument("--pretty", dest="pretty", action="store_true", default=True)
    formatting.add_argument("--no-pretty", dest="pretty", action="store_false")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = parse(
            args.image_path,
            include_raw_ocr=args.debug,
            include_diagnostics=args.debug,
        )
    except BankReceiptParserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: could not read receipt image: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: unexpected parsing failure ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1

    payload = result.model_dump(mode="json")
    if args.debug:
        diagnostics = result.diagnostics.model_dump(mode="json") if result.diagnostics else None
        payload["debug"] = {
            "raw_ocr_text": result.raw_ocr_text,
            "detection": diagnostics,
        }

    indent = 2 if args.pretty else None
    print(json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
