# Adding a new issuer

Checklist for an issuer supported **end-to-end** by `parse()` and registered in `_PARSERS`. The flow matches **UENO, BNF, and Itaú**: manual registration, no autodiscovery.

**Scope:** This guide is for full support (`Issuer` enum member + `StructuredReceiptParser` in `parsers/registry.py` with key `Issuer.<MEMBER>.value`). Detection profiles may use string literals internally, but **profile-only strings are not an equivalent substitute** for adding the enum and registry entry when you intend full `parse()` support.

## Checklist

| Step | Required? | Notes |
|------|-----------|--------|
| Add member to `Issuer` in `src/bankreceipt_parser/models/issuer.py` | **Yes** | Stable slug (e.g. `ueno`, `bnf`, `itau`). Registry keys use `Issuer.<MEMBER>.value`. |
| `ISSUER_METADATA` + `BANK_NAME_RULES` entry | Optional | Only when bank-name canonicalization is safe for extracted labels (see UENO in `normalization/registry.py`; BNF/Itaú may omit rules). |
| Product terms in `detection/signals/product_lexicon.py` | Optional | Helps text-based issuer resolution; BNF/Itaú also use profiles with `establish_issuer` without brand text in OCR. |
| Detection profiles in `detection/profiles/py/<issuer>.py` | **Yes** | Variant profiles + issuer-only profiles if needed (Itaú visual). |
| Register profiles in `detection/profiles/__init__.py` (`ALL_PROFILES`) | **Yes** | Concatenate your `ALL_<ISSUER>_PROFILES` tuple. |
| Align profile `variant` strings with `parsers/py/<issuer>/variants.py` | **Yes** | Parser `resolve_variant` and detection must agree on variant ids. |
| Implement `StructuredReceiptParser` | **Yes** | In `parsers/py/<issuer>/parser.py`; follow Atlas layout (private methods + declarative receipt build). See `parsers/base.py`. |
| Register in `parsers/registry.py` (`_PARSERS`) | **Yes** | `from bankreceipt_parser.parsers.py.<issuer> import <Issuer>ReceiptParser`. |
| Shared helpers in `parsers/common/` | Optional | Only after duplicated logic is proven (e.g. `account_type_from_text`, `payment_network_from_text`). |
| Detection tests | **Yes** | Synthetic `OCRResult` with elements when layout matters; see `tests/unit/detection/test_bnf_profile.py`, `test_itau_profile.py`. |
| Parser tests | **Yes** | Synthetic lines/OCR only; see `tests/unit/parsers/py/test_*_parser.py`. |
| Private validation on real receipts | Recommended | Gitignored folders; `scripts/evaluate_ocr.py`, `scripts/evaluate_issuer_signals.py` (see README). |
| Commit real receipt images to the repo | **No** | Privacy policy; use invented fixtures in tests. |

## Parser package layout

| State | Layout under `parsers/py/` |
|-------|----------------------------|
| **Registered parser** | `<issuer>/__init__.py`, `parser.py`, `variants.py` — public API: `from bankreceipt_parser.parsers.py.<issuer> import <Issuer>ReceiptParser, <Issuer>Variant` |
| **Stub only (not in registry)** | `<issuer>.py` with minimal `parse_text` raising `ParseError` until full support |

When promoting a stub to a registered parser, replace the flat module with a package in the same PR that adds the registry entry.

## Parser and layout expectations

- Prefer **lines + label anchors**; add `ocr.elements` geometry only where needed (see [architecture.md](architecture.md)).
- On insufficient evidence, leave fields `None` or enums `UNKNOWN`; raise `ParseError` only for variant resolution failures you cannot handle safely—not for missing optional fields.
- Do not encode institution-specific “which line is bank” rules using hard-coded competitor bank names inside the parser.

## Validation commands

```bash
ruff check .
mypy
pytest tests/unit
pytest tests/unit/detection/test_<issuer>_profile.py
pytest tests/unit/parsers/py/test_<issuer>_parser.py
```

## Related code map

| Concern | Location |
|---------|----------|
| Issuer slug enum | `models/issuer.py` |
| Detection orchestration | `detection/heuristics.py`, `detection/issuer.py` |
| Profile definitions | `detection/profiles/py/` |
| Parser implementation | `parsers/py/<issuer>/parser.py` |
| Variant enum | `parsers/py/<issuer>/variants.py` |
| Parser registry | `parsers/registry.py` |
| Public parse API | `api.py` |
| Architecture principles | [architecture.md](architecture.md) |
