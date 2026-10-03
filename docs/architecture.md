# Architecture

Developer-oriented notes on how **bankreceipt-parser** is structured today across Paraguay (`py`) issuers registered in `parsers/registry.py`. This document describes existing behavior—not a roadmap for new frameworks.

## Pipeline overview

```text
image
  → preprocessing → OCR → OCRResult (text + optional elements)
  → issuer/format detection (text, layout, visual signals on image)
  → bank-specific StructuredReceiptParser (when registered)
  → BankTransferReceipt
  → optional bank-name canonicalization at the API boundary
```

Public entry points: `parse()` (image + local OCR), `parse_receipt_text()` (pre-extracted text and optional `OCRResult`), `extract_ocr()`, `extract_text()`.

### Serialized receipt fields

`BankTransferReceipt` JSON includes:

- **`issuer`** — stable slug (e.g. `medalla_milagrosa`).
- **`issuer_display_name`** — canonical name from `ISSUER_METADATA` for that slug; `null` when the slug is not a registered `Issuer` member. Derived at serialization time, not stored on parsers and not read from OCR.

## Core principles

### Detection and parsing are separate

- **Detection** answers whether the receipt issuer/format is identified with enough confidence (`DetectionStatus`: `unknown` or `identified`). See `IssuerDetectionOutcome` in `detection/outcome.py`.
- **Parsing** fills `BankTransferReceipt` fields from OCR evidence. Success or failure does **not** change the detection outcome.
- If parsing fails with an expected `ParseError`, `parse()` / `parse_receipt_text()` return `ParseResult` with `receipt=None`, detection unchanged, and a `receipt parsing failed` warning.
- If no parser is registered for an identified issuer, the API returns `receipt=None` with a `parser not implemented` warning (`ValueError("parser_unavailable")` internally).

### Extraction vs normalization

- **Parsers** extract what appears on the receipt (names, accounts, amounts, labels). They should not invent values when evidence is missing.
- **`normalize_receipt_bank_names()`** runs in the API after parsing. It canonicalizes `sender.bank` / `recipient.bank` only when a conservative rule in `normalization/registry.py` matches extracted text. `IssuerMetadata.display_name` is for that mapping—not for filling empty bank fields.
- Do **not** use destination-bank names or other party fields as structural hints inside a parser to decide which line is “the” `bank` field for another party. Issuer detection profiles follow the same idea (e.g. BNF does not treat recipient bank text as issuer evidence).

### Prefer null and UNKNOWN over guessing

- Model defaults use `UNKNOWN` or `None` where appropriate (`Party`, optional receipt fields).
- Detection scores and profile margins are **heuristic**, not calibrated probabilities. Treat `IssuerCandidate.score` as a relative ranking aid, not a true likelihood.

## Text and lines vs layout

### Default: reconstructed lines

Registered parsers usually work from **reading-order lines** built by `lines_from_ocr()` in `parsers/common/lines.py`:

- If `OCRResult.elements` is non-empty, lines come from `reconstruct_ocr_lines()` (spatial grouping with a normalized Y tolerance).
- If `elements` is empty, lines fall back to splitting `ocr.text` on newlines.

Field extraction then uses **semantic anchors** (normalized labels such as “Destinatario”, “Para”, “Cuenta destino”) and line-local heuristics, not raw pixel coordinates.

### When layout (`elements` / bounding boxes) is used

Use spatial OCR only when line text alone cannot assign a field reliably. Current examples:

- **UENO:** pairing amount and currency tokens by relative Y/X on certain variants (`ueno_parser.py`).
- **Itaú:** recipient name beside the “Para” label using column geometry relative to anchor elements; if `ocr.elements` is missing, the parser falls back to line-based logic.

**Detection** (separate from parsing) also uses normalized regions, text-in-region signals, color bands, and vertical order—always relative geometry, not fixed screenshot pixel sizes.

### What we avoid

- Do not change global reading-order or OCR reconstruction for one issuer’s contamination; fix issuer-specific logic in that parser or its detection profiles.
- Do not rely on absolute screen coordinates tied to a single device capture when relative anchors suffice.

## Structured OCR and public API contracts

### Types

| Type | Role |
|------|------|
| `ReceiptParser` | Text-first protocol (`parse_text`). Used by stubs and direct callers. |
| `StructuredReceiptParser` | Extends `ReceiptParser` with `resolve_variant(ocr, …)` and `parse_ocr(ocr, …)`. Required for entries in `parsers/registry.py`. |
| `OCRResult` | `text`, `elements` (`OCRTextElement` with normalized bboxes), image dimensions, optional OCR warnings. |
| `OCREngine` | `extract_text(bytes)` only. |
| `StructuredOCREngine` | Adds `run_structured_on_image()` → full `OCRResult`. Defined in `ocr/engine.py`; default implementation is `TesseractOCREngine`. |

There is **no** plugin autodiscovery: parsers and detection profiles are registered manually.

### `parse(image)`

1. Runs `extract_ocr_with_oriented_image()` (default engine: Tesseract structured OCR).
2. Calls `detect_issuer(text=…, ocr=…, image=oriented_image)` so **visual** detection signals (e.g. Itaú header color) can run.
3. On `identified`, resolves variant and calls the registered `StructuredReceiptParser`.
4. Canonicalizes bank names on the result.

If the injected `OCREngine` is not a `StructuredOCREngine`, the pipeline still returns `OCRResult` but with **`elements=[]`** (text-only OCR). Parsers keep working for many fields via the line fallback; layout-specific logic may degrade.

The API also duck-checks that the registry parser exposes callable `parse_ocr` and `resolve_variant` before use (`_structured_ocr_parser`).

### `parse_receipt_text(text, ocr=…)`

- Runs detection on supplied text / `OCRResult` **without** passing a receipt image, so **visual-only** profiles do not run unless you call `detect_issuer(..., image=…)` yourself.
- If `ocr` is omitted, builds `OCRResult(text=text, elements=[], …)`.
- Same parsing and normalization rules as `parse()` once detection is `identified`.

`parse_text()` on a concrete parser builds a minimal `OCRResult` and delegates to `parse_ocr()`; that does not by itself provide rich layout unless the caller supplied structured `ocr`.

## Further reading

- [Adding a new issuer](adding-an-issuer.md) — checklist for end-to-end support via `parse()`.
