"""INTERFISA transfer receipt parsers."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifier, TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.models.party import Party
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.amounts import parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import (
    collect_name_block,
    find_line_index,
    lines_from_ocr,
    normalize_label,
    value_on_same_line,
)
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.py.interfisa.variants import InterfisaVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_TRANSACTION_NUMBER = re.compile(r"^\d{6,12}$")
_ACCOUNT_DIGITS = re.compile(r"^\d{6,18}$")
_DOCUMENT_VALUE = re.compile(
    r"^(?:(?:ci|ruc|pasaporte)\s*[-–]?\s*)?(?P<id>\d[\d.\-/]*)$",
    re.I,
)


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = _GROUPED_AMOUNT.search(line)
    if match:
        return parse_decimal_amount(match.group(0))
    return None


def _label_value(lines: list[str], *label_parts: str) -> str | None:
    """Read a colon value or the next non-label line after a partial label match."""
    needles = tuple(normalize_label(part) for part in label_parts)
    for index, line in enumerate(lines):
        norm = normalize_label(line)
        if not all(needle in norm for needle in needles):
            continue
        inline = value_on_same_line(line, label_parts[-1])
        if inline:
            return inline.strip()
        for follow in lines[index + 1 : index + 4]:
            follow_norm = normalize_label(follow)
            if not follow.strip():
                continue
            if any(needle in follow_norm for needle in needles):
                continue
            return follow.strip()
    return None


def _occurred_at_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if parse_occurred_at(line) is not None:
            return index
    return None


def _normalize_document(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip()
    match = _DOCUMENT_VALUE.match(cleaned)
    if match:
        return match.group("id").replace(".", "").replace("-", "").strip() or None
    digits = re.sub(r"\D", "", cleaned)
    return digits or cleaned or None


class InterfisaReceiptParser:
    """Parse INTERFISA transfer receipts from OCR."""

    issuer = Issuer.INTERFISA
    supported_variants = frozenset(variant.value for variant in InterfisaVariant)

    def parse_text(
        self,
        text: str,
        *,
        country_code: str | None = "py",
        ocr: OCRResult | None = None,
    ) -> BankTransferReceipt:
        base = ocr or OCRResult(text=text, elements=[], image_width=1, image_height=1)
        if not base.text:
            base = base.model_copy(update={"text": text})
        return self.parse_ocr(base, country_code=country_code)

    def parse_ocr(
        self,
        ocr: OCRResult,
        *,
        country_code: str | None = "py",
        variant: str | None = None,
    ) -> BankTransferReceipt:
        lines = lines_from_ocr(ocr)
        selected = self.resolve_variant(ocr, variant=variant)
        if selected == InterfisaVariant.TRANSFER_LOADED:
            return self._parse_transfer_loaded(ocr, lines, country_code=country_code)
        raise ParseError(f"Unsupported INTERFISA receipt variant: {selected!r}.")

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported INTERFISA receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text)

    def _detect_variant(self, full_text: str) -> str:
        norm = normalize_label(full_text)
        if "transferencia cargada" in norm:
            return InterfisaVariant.TRANSFER_LOADED
        raise ParseError("Could not infer INTERFISA receipt variant from OCR.")

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text)
        if "gs" in norm or "guarani" in norm or "pyg" in norm:
            return "PYG"
        return "PYG"

    def _parse_transfer_loaded(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount(lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(lines),
            status=TransferStatus.COMPLETED,
            raw_status="TRANSFERENCIA CARGADA",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
            concept=self._parse_concept(lines),
            payment_network=None,
            country_code=country_code,
        )

    def _parse_amount(self, lines: list[str]) -> Decimal | None:
        monto_index = find_line_index(lines, "monto deb")
        search_from = monto_index if monto_index is not None else 0
        for line in lines[search_from : search_from + 6]:
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        for line in lines:
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        return None

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        index = _occurred_at_line_index(lines)
        if index is not None:
            parsed = parse_occurred_at(lines[index])
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        raw = _label_value(lines, "transaccion")
        if raw and _TRANSACTION_NUMBER.fullmatch(raw.strip()):
            return [
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.OPERATION,
                    value=raw.strip(),
                    label="Nro de Transacción",
                )
            ]
        for index, line in enumerate(lines):
            norm = normalize_label(line)
            if "transaccion" not in norm:
                continue
            for follow in lines[index + 1 : index + 3]:
                candidate = follow.strip()
                if _TRANSACTION_NUMBER.fullmatch(candidate):
                    return [
                        TransactionIdentifier(
                            kind=TransactionIdentifierKind.OPERATION,
                            value=candidate,
                            label="Nro de Transacción",
                        )
                    ]
        return []

    def _parse_sender(self, lines: list[str]) -> Party | None:
        cuenta_index = find_line_index(lines, "cuenta deb")
        if cuenta_index is None:
            cuenta_index = find_line_index(lines, "cuenta debito")
        dt_index = _occurred_at_line_index(lines)
        name: str | None = None
        if dt_index is not None and cuenta_index is not None and cuenta_index > dt_index:
            raw_name = collect_name_block(lines, dt_index + 1, max_lines=3)
            if raw_name:
                name = natural_name_from_single_comma(raw_name)
        account: str | None = None
        if cuenta_index is not None:
            for line in lines[cuenta_index + 1 : cuenta_index + 3]:
                digits = line.strip()
                if _ACCOUNT_DIGITS.fullmatch(digits):
                    account = digits
                    break
        if not name and not account:
            return None
        return Party(name=name, account=account)

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        transaction_id = self._parse_identifiers(lines)
        txn_value = transaction_id[0].value if transaction_id else None
        bank: str | None = None
        account: str | None = None
        for index, line in enumerate(lines):
            norm = normalize_label(line)
            if "documento" in norm and "benefici" in norm:
                continue
            if ("banco" in norm or norm.startswith("anco ")) and "benefici" in norm:
                if index + 1 < len(lines):
                    bank = lines[index + 1].strip()
                break
        amount_index = None
        for index, line in enumerate(lines):
            if _gs_amount_in_line(line) is not None:
                amount_index = index
                break
        bank_label_index = find_line_index(lines, "beneficiar")
        if bank_label_index is not None:
            credit_start = amount_index + 1 if amount_index is not None else 0
            for line in lines[credit_start:bank_label_index]:
                digits = line.strip()
                if not _ACCOUNT_DIGITS.fullmatch(digits):
                    continue
                if txn_value and digits == txn_value:
                    continue
                if len(digits) >= 8:
                    account = digits
                    break
        document_raw = _label_value(lines, "documento", "benefici")
        document_identifier = _normalize_document(document_raw)
        name = _label_value(lines, "nombre", "benefici")
        if name:
            name = natural_name_from_single_comma(name.strip())
        if bank:
            bank = re.sub(r"\s+", " ", bank).strip()
        if not bank and not account and not document_identifier and not name:
            return None
        return Party(
            name=name,
            bank=bank,
            account=account,
            document_identifier=document_identifier,
        )

    def _parse_concept(self, lines: list[str]) -> str | None:
        amount_index = None
        for index, line in enumerate(lines):
            if _gs_amount_in_line(line) is not None:
                amount_index = index
                break
        if amount_index is None:
            return _label_value(lines, "motivo")
        fallback: str | None = None
        for line in lines[amount_index + 1 :]:
            norm = normalize_label(line)
            stripped = line.strip()
            if not stripped:
                continue
            if "benefici" in norm or "documento" in norm:
                break
            if _ACCOUNT_DIGITS.fullmatch(stripped):
                break
            if _gs_amount_in_line(line) is not None:
                continue
            if "motivo" in norm or len(stripped) <= 3:
                continue
            if stripped.startswith("$") or re.fullmatch(r"[\d\s$]+", stripped):
                continue
            if " " in stripped:
                return stripped
            if fallback is None:
                fallback = stripped
        return fallback or _label_value(lines, "motivo")
