"""Medalla Milagrosa cooperative transfer receipt parsers."""

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
from bankreceipt_parser.parsers.common.lines import (
    find_line_index,
    lines_from_ocr,
    normalize_label,
    value_on_same_line,
)
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.medalla_milagrosa.variants import MedallaMilagrosaVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}
_MEDALLA_DATETIME = re.compile(
    r"(\d{1,2})\s+([a-z]{3,4})\.?\s+(\d{4}),?\s+(\d{1,2}):(\d{2}):(\d{2})\s+p\.?\s*m\.?",
    re.I,
)
_CUENTA_DIGITS = re.compile(r"cuenta\s*n[°º]?\s*(\d{6,18})", re.I)
_COMPROBANTE_DIGITS = re.compile(r"comprobante\s*(\d{6,})", re.I)


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = _GROUPED_AMOUNT.search(line)
    if match:
        return parse_decimal_amount(match.group(0))
    return None


def _amount_from_lines(lines: list[str]) -> Decimal | None:
    for line in lines:
        amount = _gs_amount_in_line(line)
        if amount is not None:
            return amount
    return None


def _short_section_index(lines: list[str], heading: str) -> int | None:
    """Locate a De/Para-style section heading without matching longer labels."""
    target = normalize_label(heading)
    for index, line in enumerate(lines):
        norm = normalize_label(line)
        if norm == target:
            return index
        if norm.endswith(f" {target}") and len(norm) <= len(target) + 3:
            return index
    return None


def _strip_name_line_noise(line: str) -> str:
    stripped = line.strip()
    match = re.match(r"^(?:[^\w]*\w{1,3}\s+)?(.+)$", stripped)
    if match:
        stripped = match.group(1).strip()
    parts = stripped.split(None, 1)
    if len(parts) == 2 and len(parts[0]) <= 2 and parts[1][:1].isupper():
        stripped = parts[1]
    leading_trim = re.sub(r"^[^A-Za-zÁÉÍÓÚÑáéíóúÑ]+", "", stripped)
    return leading_trim.strip() or stripped


def _is_account_line(line: str) -> bool:
    norm = normalize_label(line)
    return "cuenta" in norm and re.search(r"\d", line) is not None


def _is_bank_line(line: str) -> bool:
    norm = normalize_label(line)
    if _is_account_line(line):
        return False
    return "banco" in norm or "sociedad anonima" in norm or "s.a" in norm


def _inline_after_label(line: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s+(.+)", line, flags=re.I)
    if match:
        return match.group(1).strip()
    return None


def _label_inline_value(lines: list[str], *label_parts: str) -> str | None:
    label = label_parts[-1]
    for index, line in enumerate(lines):
        norm = normalize_label(line)
        if normalize_label(label) not in norm:
            continue
        colon_value = value_on_same_line(line, label)
        if colon_value:
            return colon_value
        inline = _inline_after_label(line, label)
        if inline:
            return inline
        for follow in lines[index + 1 : index + 3]:
            if follow.strip():
                return follow.strip()
    return None


def _parse_medalla_datetime(text: str) -> datetime | None:
    match = _MEDALLA_DATETIME.search(text)
    if not match:
        return None
    day_s, month_s, year_s, hour_s, minute_s, second_s = match.groups()
    month = _SPANISH_MONTHS.get(month_s.casefold()[:3])
    if month is None:
        return None
    try:
        hour = int(hour_s)
        if hour < 12 and re.search(r"p\.?\s*m", match.group(0), flags=re.I):
            hour += 12
        return datetime(
            int(year_s),
            month,
            int(day_s),
            hour,
            int(minute_s),
            int(second_s),
        )
    except ValueError:
        return None


def _parse_status(lines: list[str]) -> tuple[TransferStatus, str | None]:
    for line in lines[:4]:
        norm = normalize_label(line)
        if "en proceso" in norm:
            return TransferStatus.PENDING, line.strip()
        if "realizada" in norm or "exitosa" in norm or "confirmad" in norm:
            return TransferStatus.COMPLETED, line.strip()
    return TransferStatus.UNKNOWN, None


def _parse_transaction_identifiers(lines: list[str]) -> list[TransactionIdentifier]:
    for line in lines:
        match = _COMPROBANTE_DIGITS.search(normalize_label(line))
        if match:
            value = match.group(1)
        else:
            norm = normalize_label(line)
            if "comprobante" not in norm:
                continue
            digit_match = re.search(r"\d{10,}", line)
            if not digit_match:
                continue
            value = digit_match.group(0)
        return [
            TransactionIdentifier(
                kind=TransactionIdentifierKind.OPERATION,
                value=value,
                label="N° de comprobante",
            )
        ]
    return []


def _party_name_from_section(lines: list[str], start: int, end: int) -> str | None:
    for index in range(start + 1, end):
        line = lines[index].strip()
        if not line or _is_account_line(line) or _is_bank_line(line):
            continue
        cleaned = _strip_name_line_noise(line)
        return natural_name_from_single_comma(cleaned)
    return None


def _account_in_section(lines: list[str], start: int, end: int) -> str | None:
    for index in range(start + 1, end):
        match = _CUENTA_DIGITS.search(lines[index])
        if match:
            return match.group(1)
    return None


class MedallaMilagrosaReceiptParser:
    """Parse Medalla Milagrosa transfer operation receipts."""

    issuer = Issuer.MEDALLA_MILAGROSA
    supported_variants = frozenset(variant.value for variant in MedallaMilagrosaVariant)

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
        if selected != MedallaMilagrosaVariant.TRANSFER_OPERATION:
            raise ParseError(f"Unsupported Medalla Milagrosa receipt variant: {selected!r}.")
        return self._parse_transfer_operation(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Medalla Milagrosa receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "medalla milagrosa" in norm or (
            _short_section_index(lines, "de") is not None
            and _short_section_index(lines, "para") is not None
            and find_line_index(lines, "detalles") is not None
        ):
            return MedallaMilagrosaVariant.TRANSFER_OPERATION
        raise ParseError("Could not infer Medalla Milagrosa receipt variant from OCR.")

    def _parse_transfer_operation(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = _amount_from_lines(lines)
        status, raw_status = _parse_status(lines)
        de_index = _short_section_index(lines, "de")
        para_index = _short_section_index(lines, "para")
        detalles_index = find_line_index(lines, "detalles")
        sender: Party | None = None
        recipient: Party | None = None
        if de_index is not None and para_index is not None and de_index < para_index:
            sender_name = _party_name_from_section(lines, de_index, para_index)
            sender_account = _account_in_section(lines, de_index, para_index)
            if sender_name or sender_account:
                sender = Party(name=sender_name, account=sender_account, bank=None)
        if para_index is not None:
            if detalles_index is not None and detalles_index > para_index:
                end = detalles_index
            else:
                end = len(lines)
            recipient_name = _party_name_from_section(lines, para_index, end)
            recipient_account = _account_in_section(lines, para_index, end)
            recipient_bank: str | None = None
            for index in range(para_index + 1, end):
                if _is_bank_line(lines[index]):
                    recipient_bank = lines[index].strip()
                    break
            if recipient_name or recipient_account or recipient_bank:
                recipient = Party(
                    name=recipient_name,
                    account=recipient_account,
                    bank=recipient_bank,
                )
        concept = _label_inline_value(lines, "concepto")
        occurred_at = _parse_medalla_datetime(ocr.text)
        if occurred_at is None:
            for line in lines:
                occurred_at = _parse_medalla_datetime(line)
                if occurred_at is not None:
                    break
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=_parse_transaction_identifiers(lines),
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency="PYG" if amount is not None else None,
            occurred_at=occurred_at,
            sender=sender,
            recipient=recipient,
            concept=concept,
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )
