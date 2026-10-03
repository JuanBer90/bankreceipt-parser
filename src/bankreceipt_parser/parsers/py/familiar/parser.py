"""Banco Familiar transfer receipt parsers."""

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
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.familiar.variants import FamiliarVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_DD_MON_YYYY_TIME = re.compile(
    r"(\d{1,2})[-/]([a-z]{3})[-/](\d{4})\s+(\d{1,2}):(\d{2})\s*h",
    re.I,
)
_MONTHS = {
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


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = _GROUPED_AMOUNT.search(line)
    if match:
        return parse_decimal_amount(match.group(0))
    return None


def _section_index(lines: list[str], heading: str) -> int | None:
    target = normalize_label(heading)
    for index, line in enumerate(lines):
        if target in normalize_label(line) and len(normalize_label(line)) <= len(target) + 12:
            return index
    return find_line_index(lines, heading)


def _colon_field_value(lines: list[str], *label_parts: str) -> str | None:
    needles = tuple(normalize_label(part) for part in label_parts)
    for index, line in enumerate(lines):
        norm = normalize_label(line)
        if not all(needle in norm for needle in needles):
            continue
        if ":" in line:
            value = line.split(":", 1)[1].strip()
            if value:
                return value
        for follow in lines[index + 1 : index + 3]:
            follow_norm = normalize_label(follow)
            if follow.strip() and not any(
                token in follow_norm
                for token in ("entidad", "cliente", "nro", "moneda", "referencia", "razon")
            ):
                return follow.strip()
    return None


def _masked_from_line(line: str) -> str | None:
    if "*" not in line and "•" not in line:
        return None
    match = re.search(r"(\d[\d\-]*[*•]+[\d*•]*)", line)
    if match:
        return match.group(1).strip()
    if re.search(r"[*•]{4,}", line):
        cleaned = re.sub(r"\s+", "", line.strip())
        return cleaned or None
    return None


def _parse_dd_mon_yyyy_time(text: str) -> datetime | None:
    match = _DD_MON_YYYY_TIME.search(text)
    if not match:
        return None
    day_s, month_s, year_s, hour_s, minute_s = match.groups()
    month = _MONTHS.get(month_s.casefold()[:3])
    if month is None:
        return None
    return parse_occurred_at(f"{day_s}/{month:02d}/{year_s} {hour_s}:{minute_s}:00")


def _account_digits(line: str) -> str | None:
    match = re.search(r"\b(\d{6,18})\b", line)
    return match.group(1) if match else None


def _trim_bank_ocr_noise(line: str) -> str:
    """Drop currency/UI fragments OCR often merges onto the bank name line."""
    text = line.strip()
    lower = text.casefold()
    for marker in (" gs ", " gs.", " gs+", " + n"):
        idx = lower.find(marker)
        if idx > 0:
            text = text[:idx].strip()
            lower = text.casefold()
    return text


class FamiliarReceiptParser:
    """Parse Banco Familiar transfer receipts from OCR."""

    issuer = Issuer.FAMILIAR
    supported_variants = frozenset(variant.value for variant in FamiliarVariant)

    def parse_text(
        self,
        text: str,
        *,
        qr_data: str | None = None,
        country_code: str | None = "py",
        ocr: OCRResult | None = None,
    ) -> BankTransferReceipt:
        _ = qr_data
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
        if selected == FamiliarVariant.TRANSFER_LOADED:
            return self._parse_transfer_loaded(ocr, lines, country_code=country_code)
        if selected == FamiliarVariant.TRANSFER_CONFIRMED:
            return self._parse_transfer_confirmed(ocr, lines, country_code=country_code)
        raise ParseError(f"Unsupported Familiar receipt variant: {selected!r}.")

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Familiar receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia cargada" in norm and "exito" in norm:
            return FamiliarVariant.TRANSFER_LOADED
        if "otras entidades" in norm and "confirmada" in norm:
            return FamiliarVariant.TRANSFER_CONFIRMED
        raise ParseError("Could not infer Familiar receipt variant from OCR.")

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text)
        if "pyg" in norm or "gs" in norm or "guarani" in norm:
            return "PYG"
        return "PYG" if amount is not None else None

    def _parse_transfer_loaded(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_loaded_amount(lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=[],
            status=TransferStatus.COMPLETED,
            raw_status="Transferencia cargada con éxito",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_loaded_datetime(ocr.text),
            sender=self._parse_loaded_sender(lines),
            recipient=self._parse_loaded_recipient(lines),
            concept=None,
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_transfer_confirmed(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_confirmed_amount(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_confirmed_identifiers(lines, ocr.text),
            status=TransferStatus.COMPLETED,
            raw_status="TRANSFERENCIA A OTRAS ENTIDADES CONFIRMADA",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_confirmed_datetime(lines, ocr.text),
            sender=self._parse_confirmed_sender(lines),
            recipient=self._parse_confirmed_recipient(lines),
            concept=None,
            payment_network=None,
            country_code=country_code,
        )

    def _parse_loaded_amount(self, lines: list[str]) -> Decimal | None:
        index = _section_index(lines, "monto a enviar")
        if index is None:
            index = find_line_index(lines, "monto")
        if index is None:
            return None
        for line in lines[index : index + 4]:
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        return None

    def _parse_loaded_datetime(self, full_text: str) -> datetime | None:
        parsed = _parse_dd_mon_yyyy_time(full_text)
        if parsed is not None:
            return parsed
        return parse_occurred_at(full_text)

    def _parse_loaded_sender(self, lines: list[str]) -> Party | None:
        start = _section_index(lines, "enviado por")
        cuenta_index = find_line_index(lines, "cuenta n")
        if start is None:
            return None
        end = cuenta_index if cuenta_index is not None and cuenta_index > start else start + 3
        name: str | None = None
        for line in lines[start + 1 : end]:
            norm = normalize_label(line)
            if "cuenta" in norm or "fecha" in norm:
                break
            if len(line.strip()) >= 3 and not _gs_amount_in_line(line):
                name = natural_name_from_single_comma(line.strip())
                break
        masked: str | None = None
        if cuenta_index is not None:
            for line in lines[cuenta_index : cuenta_index + 2]:
                masked = _masked_from_line(line) or masked
        if not name and not masked:
            return None
        return Party(name=name, masked_account=masked)

    def _parse_loaded_recipient(self, lines: list[str]) -> Party | None:
        start = _section_index(lines, "a la cuenta de")
        end = _section_index(lines, "enviado por")
        if start is None or end is None or end <= start:
            return None
        name_parts: list[str] = []
        bank: str | None = None
        account: str | None = None
        for line in lines[start + 1 : end]:
            norm = normalize_label(line)
            if "banco" in norm or re.search(r"\bs\.?\s*a\.?\s*e", norm):
                bank = _trim_bank_ocr_noise(line)
                continue
            digits = _account_digits(line)
            if digits and len(digits) >= 9:
                account = digits
                continue
            if len(line.strip()) >= 4 and "n°" not in norm and "gs" not in norm:
                name_parts.append(line.strip())
        name = " ".join(name_parts).strip() or None
        if name:
            name = natural_name_from_single_comma(name)
        if not name and not bank and not account:
            return None
        return Party(name=name, bank=bank, account=account)

    def _parse_confirmed_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        raw = _colon_field_value(lines, "moneda", "monto")
        if raw:
            match = re.search(r"([\d.]+)", raw)
            if match:
                return parse_decimal_amount(match.group(1))
        match = re.search(r"PYG\s*([\d.]+)", full_text, flags=re.I)
        if match:
            return parse_decimal_amount(match.group(1))
        return None

    def _parse_confirmed_datetime(self, lines: list[str], full_text: str) -> datetime | None:
        for index, line in enumerate(lines):
            if "fecha" in normalize_label(line) and "operacion" in normalize_label(line):
                chunk = line
                if index + 1 < len(lines):
                    chunk = f"{chunk} {lines[index + 1]}"
                parsed = parse_occurred_at(chunk)
                if parsed is not None:
                    return parsed
        return parse_occurred_at(full_text)

    def _parse_confirmed_identifiers(
        self,
        lines: list[str],
        full_text: str,
    ) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        operation = _colon_field_value(lines, "nro", "operacion")
        if operation and re.fullmatch(r"\d{6,14}", operation.strip()):
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.OPERATION,
                    value=operation.strip(),
                    label="Nro. de Operación",
                )
            )
        reference = _colon_field_value(lines, "referencia")
        if reference and reference.upper().startswith("FAMI"):
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.REFERENCE,
                    value=reference.strip(),
                    label="Referencia",
                )
            )
        return identifiers

    def _parse_confirmed_sender(self, lines: list[str]) -> Party | None:
        name = _colon_field_value(lines, "cliente", "pagador")
        if name:
            name = natural_name_from_single_comma(name.lstrip("| ").strip())
        masked: str | None = None
        for line in lines:
            norm = normalize_label(line)
            if "cuenta" in norm and "pagador" in norm:
                masked = _masked_from_line(line)
                if masked:
                    break
        bank = _colon_field_value(lines, "entidad", "pagadora")
        if not name and not bank and not masked:
            return None
        return Party(name=name, bank=bank, masked_account=masked)

    def _parse_confirmed_recipient(self, lines: list[str]) -> Party | None:
        name = _colon_field_value(lines, "cliente", "beneficiario")
        if name:
            name = natural_name_from_single_comma(name.lstrip("| ").strip())
        bank = _colon_field_value(lines, "entidad", "beneficiaria")
        account: str | None = None
        benef_idx = find_line_index(lines, "cliente beneficiario")
        if benef_idx is None:
            benef_idx = find_line_index(lines, "beneficiario")
        if benef_idx is not None:
            for line in lines[benef_idx : benef_idx + 6]:
                norm = normalize_label(line)
                if "pagador" in norm:
                    continue
                digits = _account_digits(line)
                if digits and len(digits) >= 9:
                    account = digits
                    break
        if not name and not bank and not account:
            return None
        return Party(name=name, bank=bank, account=account)
