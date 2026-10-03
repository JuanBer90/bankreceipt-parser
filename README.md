# bankreceipt-parser

Open-source Python library to **parse and normalize bank transfer receipt images** into structured, typed data. Processing is **local and deterministic**: OCR runs on your machine with [Tesseract](https://github.com/tesseract-ocr/tesseract). No cloud APIs and no generative AI.

**Scope:** Paraguay transfer comprobantes (`country_code` `py` in parsers). The package layout is country-extensible, but **0.1.0** ships parsers and detection for Paraguayan issuers only.

**Status:** Alpha (`0.1.0`). Behavior and field coverage may change between minor releases while the API stabilizes.

## What it does

1. Load a receipt image (PNG, JPEG, or WEBP).
2. Preprocess and run Tesseract OCR (primary pass plus a supplemental pass merged into structured `OCRResult`).
3. Detect issuer and receipt layout variant.
4. Parse with a bank-specific parser when registered.
5. Return a `ParseResult` with an optional `BankTransferReceipt`, warnings, and optional diagnostics.

The library **extracts and normalizes** what appears on the receipt. It does not provide fraud checks, duplicate detection, databases, or web services.

## Requirements

- **Python 3.12.x** (`requires-python >=3.12,<3.13`)
- **Tesseract OCR** installed on the system (`pytesseract` is only a Python binding)

Spanish (`spa`) language data is strongly recommended for Paraguayan receipts. When both `spa` and `eng` are available, OCR uses `spa+eng`; otherwise the library falls back to `eng` and may add a warning.

## Install

```bash
pip install bankreceipt-parser
```

Development (from a clone):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

## Tesseract setup

Install the Tesseract **binary** for your OS (not included in the wheel).

**macOS (Homebrew):**

```bash
brew install tesseract tesseract-lang
```

**Debian/Ubuntu:**

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-spa
```

Verify:

```bash
tesseract --version
```

## Quick start

```python
from bankreceipt_parser import parse

result = parse("path/to/comprobante.png")

if result.receipt is None:
    print("Could not parse:", result.warnings)
else:
    r = result.receipt
    print(r.issuer, r.issuer_display_name)
    print(r.amount, r.currency)
    print(r.sender)
    print(r.recipient)
```

Use `include_raw_ocr=True` or `include_diagnostics=True` only when debugging; `raw_ocr_text` is omitted from default serialization.

## Supported issuers (Paraguay)

Each row is the stable **`issuer` slug** returned on `BankTransferReceipt`. Display names come from issuer metadata (`issuer_display_name`), not from OCR.

| Slug | Display name |
|------|----------------|
| `ueno` | UENO BANK S.A. |
| `bnf` | BANCO NACIONAL DE FOMENTO |
| `itau` | BANCO ITAU PARAGUAY S.A. |
| `gnb` | BANCO GNB PARAGUAY S.A.E.C.A. |
| `atlas` | BANCO ATLAS S.A. |
| `continental` | BANCO CONTINENTAL S.A.E.C.A. |
| `comecipar` | COOP COOMECIPAR LTDA |
| `bancop` | BANCOP S.A. |
| `basa` | BANCO BASA S.A.E.C.A. |
| `eclub` | eCLUB |
| `eko` | EKO |
| `familiar` | BANCO FAMILIAR S.A.E.C.A. |
| `mango` | MANGO |
| `interfisa` | INTERFISA BANCO S.A.E.C.A. |
| `financiera_pyj` | FINANCIERA PARAGUAYO JAPONESA S.A.E.C.A. |
| `medalla_milagrosa` | COOPERATIVA MEDALLA MILAGROSA LTDA. |
| `sudameris` | SUDAMERIS BANK S.A.E.C.A. |
| `vaquita` | VAQUITA |
| `zeta` | ZETA BANCO S.A.E.C.A. |

Some issuers expose multiple layout **variants** (selected during detection). Field coverage depends on the variant and OCR quality.

## Public API

Symbols exported from `bankreceipt_parser` (see `__all__` in the package):

| Symbol | Role |
|--------|------|
| `parse` | Main entry: image path or bytes → `ParseResult` |
| `parse_receipt_image` | Alias of `parse` |
| `parse_receipt_text` | Parse pre-extracted text / optional `OCRResult` without running OCR on an image |
| `extract_text` | OCR only → normalized `str` |
| `extract_ocr` | OCR only → `OCRResult` |
| `ParseResult` | `receipt`, `warnings`, optional `raw_ocr_text`, optional `diagnostics` |
| `BankTransferReceipt` | Normalized receipt model |
| `Party`, `BankParty` | Sender/recipient (and optional bank-level party) |
| `TransactionIdentifier`, `TransactionIdentifierKind` | Ticket/operation/reference IDs when extracted |
| `TransferStatus`, `AccountType` | Enums for status and account type |
| `IssuerDetectionOutcome`, `DetectionStatus` | Exposed for diagnostics (`include_diagnostics=True`) |
| `TesseractOCREngine`, `OCREngine`, `NotImplementedOCREngine` | OCR backends |
| `OCRResult`, `OCRTextElement`, `NormalizedBoundingBox` | Structured OCR types |
| `StructuredReceiptParser`, `ReceiptParser`, `GenericReceiptParser` | Parser protocols / stub for extensions |
| Exception types | `ParseError`, `OCRError`, `OCRUnavailableError`, etc. |

Issuer slugs and metadata: `from bankreceipt_parser.models import Issuer, IssuerMetadata, metadata_for`.

### `ParseResult` and warnings

- **`receipt`:** `BankTransferReceipt` on success, otherwise `None`.
- **`warnings`:** Non-fatal messages (OCR language fallback, unknown issuer, parse failure, missing parser, etc.).
- Detection outcome is **not** downgraded when parsing fails; check `receipt` and warnings together.

### Unknown issuer or format

If detection cannot identify the issuer/format with sufficient confidence, `parse()` returns `receipt=None` and a warning such as *Issuer/format could not be determined; receipt parsing skipped.* This is not raised as an exception.

### `issuer` vs party banks

- **`issuer`:** Product or institution that **issued the receipt UI** (stable slug, e.g. `ueno`).
- **`issuer_display_name`:** Canonical name from library metadata for that slug (computed field).
- **`sender.bank` / `recipient.bank`:** Counterparty banks **as printed on the receipt**, after conservative normalization. They may differ from `issuer` (e.g. transfer to another bank).

### Transaction identifiers

`transaction_identifiers` lists structured IDs (comprobante, operation, reference, etc.) when the parser extracts them. Kinds are described by `TransactionIdentifierKind`.

### Image formats

**PNG, JPEG, WEBP** via path or bytes. **PDF is not supported** in 0.1.0.

## Limitations

- Output quality depends on OCR and photo quality.
- Not every field is present on every layout variant.
- No PDF input, no batch service, no ML-based repair.
- Unit tests mock Tesseract; CI does not require the binary. Optional integration tests may use a local Tesseract install and private images (not shipped with the package).

## Privacy

Images and OCR text are processed **locally**. Do not commit real comprobantes or personal financial data to the repository. Use synthetic fixtures in tests.

## Development

```bash
ruff check .
mypy
pytest tests/
```

Developer docs:

- [Architecture](docs/architecture.md)
- [Adding an issuer](docs/adding-an-issuer.md)

Optional local scripts (not installed with the package): `scripts/evaluate_ocr.py`, `scripts/evaluate_issuer_signals.py` against a **private** image directory.

## License

MIT — see [LICENSE](LICENSE).
