# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Fixed

- **`parse()` / `parse_receipt_text()` handle expected `ParseError`:** Registered bank parsers no longer abort the public API when parsing fails (e.g. unsupported or uninferable receipt variant). Detection stays **`identified`**; the failure is represented with **`receipt=None`** and a **`receipt parsing failed`** warning, matching the documented separation of detection and parsing.

### Changed

- **`DetectionStatus` is identification-only:** `unknown` (not identified with sufficient confidence) and `identified` (issuer and/or format variant identified). Removed `unsupported` and `supported`, which mixed detection with parser availability.
- **`IssuerDetectionOutcome` is unchanged by parsing:** `parse()` / `parse_receipt_text()` diagnostics use the same detection outcome as `detect_issuer()`; whether parsing succeeded is indicated by `ParseResult.receipt`, optional `ParseDiagnostics.parser_variant`, and warnings—not by mutating `detection.status`.

### Added

- **GNB issuer (`gnb`):** Detection for `transfer_success` and `spi_movement_detail` (institutional reference `BGNBPYP…` plus SPI transfer context); registered `GnbReceiptParser` with lines-first field extraction.
- **`payment_network_from_text`:** Recognize **SPI** in addition to SIP.
- **`StructuredReceiptParser` protocol:** Public typing contract for registry parsers (`parse_text`, `resolve_variant`, `parse_ocr`) used by `parse()` after OCR; `ReceiptParser` remains text-first for stubs.
- Initial project structure and packaging.
- Domain model skeletons for normalized bank transfer receipts.
- OCR abstraction, issuer detection, and country-specific parser layout (Paraguay `py` namespace planned).
