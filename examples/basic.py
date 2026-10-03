"""Minimal example: OCR and stub parsing entry points."""

from bankreceipt_parser import ParseResult, __version__, extract_text, parse_receipt_text


def main() -> None:
    print(f"bankreceipt-parser {__version__}")
    print("OCR: extract_text(path_or_bytes) — see README")
    result: ParseResult = parse_receipt_text("sample text placeholder")
    print(result.model_dump())
    _ = extract_text  # public API


if __name__ == "__main__":
    main()
