# bankreceipt-parser

Open-source Python library to **parse and normalize bank transfer receipts** into structured data.

Initial development targets **Paraguay** (`parsers/py/`), but the layout is **country-extensible** (e.g. future `ar`, `br`, `cl` packages). No generative AI or external AI APIs are required; OCR is intended to run **locally** on your machine.

> **Status:** Early bootstrap. **UENO, BNF, Itaú, and GNB** transfer receipts can be parsed end-to-end via `parse()` when issuer detection and the parser registry match. Other issuer directories may remain stubs.

## Scope

This library focuses on **extraction and normalization** of receipt data only. It does not provide databases, duplicate/fraud detection, web APIs, or persistence.

## OCR (local)

Extract plain text from receipt images with **`extract_text`** — no bank field parsing yet:

```python
from bankreceipt_parser import extract_ocr, extract_text

text = extract_text("receipt.jpg")  # str | pathlib.Path | bytes (PNG/JPEG/WEBP)
structured = extract_ocr("receipt.jpg")  # text + normalized bounding boxes

result = parse("receipt.jpg")  # OCR + detection + registered parser when matched
# result.receipt.transaction_identifiers, .sender, .recipient, ...
```

- OCR runs **entirely on your machine**; images and OCR output are **not** sent to any external service.
- Supported inputs: **PNG, JPEG, WEBP** (not PDF yet).
- **UENO, BNF, Itaú, and GNB** are implemented for `parse(...)` when detection identifies the issuer and a parser is registered. Other issuers may be detected but not yet parsed.

### System dependency: Tesseract

OCR uses [Tesseract](https://github.com/tesseract-ocr/tesseract) via `pytesseract`. **Installing `pytesseract` does not install the Tesseract binary.** Install Tesseract separately for your OS.

- **Spanish (`spa`) language data** is strongly recommended for Paraguayan receipts. When both `spa` and `eng` are installed, OCR uses `spa+eng`. If `spa` is missing, the library falls back to `eng` with a warning.
- Unit tests mock Tesseract and do **not** require the binary in CI. An optional integration test runs locally when Tesseract is installed.

### Local OCR evaluation (private datasets)

Use the development script on a **gitignored** directory you provide (never commit real receipts):

```bash
python scripts/evaluate_ocr.py comprobantes/
python scripts/evaluate_issuer_signals.py comprobantes/
```

The script prints aggregate metrics and privacy-safe per-file stats only (no OCR text, no disk writes of extracted content).

Receipt folders label the **product/interface that generated the receipt** (`issuer`), not necessarily a bank identity. Normalized models will keep `issuer` separate from fields such as `sender.bank` or `payment_network`.

## Requirements

- Python **3.12.x** (project pins `>=3.12,<3.13`)
- [asdf](https://asdf-vm.com/) (recommended for Python version management)

## Development setup

1. Install the asdf Python plugin if needed:

   ```bash
   asdf plugin add python https://github.com/asdf-community/asdf-python.git
   ```

2. Install and select Python 3.12.13 (this repo includes `.python-version`):

   ```bash
   asdf install python 3.12.13
   cd bankreceipt-parser
   asdf local python 3.12.13   # or rely on .python-version
   ```

3. Create a virtual environment and install in editable mode with dev tools:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -U pip
   python -m pip install -e ".[dev]"
   ```

4. Run checks:

   ```bash
   ruff check .
   mypy
   pytest --cov=bankreceipt_parser
   ```

## Developer documentation

- [Architecture and OCR/parser contracts](docs/architecture.md)
- [Adding a new issuer](docs/adding-an-issuer.md)

## Architecture

Receipt processing is split so **OCR stays separate from parsing**:

```text
image
  ├──> preprocessing -> OCR -> raw text
  └──> QR decoder
                     ↓
             issuer detection
                     ↓
            bank-specific parser
                     ↓
          normalized BankTransferReceipt
```

- **`OCREngine` / `StructuredOCREngine`**: OCR backends; default `parse()` uses structured OCR (`OCRResult` with text and bounding boxes).
- **Registered parsers**: implement `StructuredReceiptParser` (`parse_ocr`, `resolve_variant`) over `OCRResult`, not raw images. See [docs/architecture.md](docs/architecture.md).
- **`BankTransferReceipt`**: normalized domain model.
- **`ParseResult`**: wraps the receipt plus metadata (`raw_ocr_text`, `warnings`).

## Privacy

Do **not** commit real bank receipt images or personal financial data. Use synthetic fixtures with invented data under `tests/fixtures/`. `.gitignore` excludes common private fixture paths.

## License

MIT — see [LICENSE](LICENSE).
