# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-03

First public release.

### Added

- Local, deterministic pipeline: image preprocessing, Tesseract OCR (structured `OCRResult` with supplemental merge), issuer/format detection, and bank-specific parsing into `BankTransferReceipt`.
- Paraguay parsers and detection for 19 issuers: `ueno`, `bnf`, `itau`, `gnb`, `atlas`, `continental`, `comecipar`, `bancop`, `basa`, `eclub`, `eko`, `familiar`, `mango`, `interfisa`, `financiera_pyj`, `medalla_milagrosa`, `sudameris`, `vaquita`, `zeta`.
- Public API: `parse`, `parse_receipt_image`, `parse_receipt_text`, `extract_text`, `extract_ocr`.
- Typed models: `ParseResult`, `BankTransferReceipt`, `Party`, `TransactionIdentifier`, enums for status and account type; `issuer_display_name` from issuer metadata.
- Conservative bank-name normalization for extracted `sender.bank` / `recipient.bank` at the API boundary.
- Warnings for unknown issuer/format, missing parser, and parse failures without changing detection status.
- Optional `include_raw_ocr` and `include_diagnostics` on parse entry points.

### Notes

- Requires Python 3.12.x and a system Tesseract installation (Spanish language data recommended).
