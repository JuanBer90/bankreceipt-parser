"""Vaquita transfer comprobante parsers."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import TransferStatus
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.models.party import Party
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.amounts import parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.py.vaquita.variants import VaquitaVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_ACCOUNT_DIGITS = re.compile(r"^\d{5,18}$")
_SPANISH_FULL_MONTH = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})\s+a\s+las\s+(\d{1,2}):(\d{2})",
    re.I,
)
_FULL_MONTHS: dict[str, int] = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = _GROUPED_AMOUNT.search(line)
    if match:
        return parse_decimal_amount(match.group(0))
    return None


def _label_value(line: str, *label_parts: str) -> str | None:
    norm = normalize_label(line)
    needles = tuple(normalize_label(part) for part in label_parts)
    if not all(needle in norm for needle in needles):
        return None
    if ":" in line:
        value = line.split(":", 1)[1].strip()
        return value or None
    pattern = r"(?i)" + r"\s+".join(re.escape(part) for part in label_parts)
    match = re.search(pattern, line)
    if match:
        tail = line[match.end() :].strip()
        return tail or None
    return None


def _field_from_lines(lines: list[str], *label_parts: str) -> str | None:
    for index, line in enumerate(lines):
        value = _label_value(line, *label_parts)
        if value:
            return value
        norm = normalize_label(line)
        if all(normalize_label(part) in norm for part in label_parts) and ":" not in line:
            for follow in lines[index + 1 : index + 2]:
                if follow.strip():
                    return follow.strip()
    return None


def _document_from_lines(lines: list[str]) -> str | None:
    for line in lines:
        match = re.match(r"^(?:ci|cl|c\.i\.)\s*:\s*(\S.+)$", line.strip(), flags=re.I)
        if not match:
            continue
        raw = match.group(1).strip()
        digits = re.sub(r"\D", "", raw)
        return digits or raw
    return None


def _parse_spanish_full_month_datetime(text: str) -> datetime | None:
    match = _SPANISH_FULL_MONTH.search(text)
    if not match:
        return None
    day_s, month_s, year_s, hour_s, minute_s = match.groups()
    month = _FULL_MONTHS.get(month_s.casefold())
    if month is None:
        return None
    return parse_occurred_at(f"{day_s}/{month:02d}/{year_s} {hour_s}:{minute_s}:00")


class VaquitaReceiptParser:
    """Parse Vaquita transfer comprobantes from OCR."""

    issuer = Issuer.VAQUITA
    supported_variants = frozenset(variant.value for variant in VaquitaVariant)

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
        if selected == VaquitaVariant.YELLOW_TRANSFER:
            return self._parse_yellow_transfer(ocr, lines, country_code=country_code)
        raise ParseError(f"Unsupported Vaquita receipt variant: {selected!r}.")

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Vaquita receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text)

    def _detect_variant(self, full_text: str) -> str:
        norm = normalize_label(full_text)
        if "comprobante de proceso" in norm or "enviado a" in norm:
            return VaquitaVariant.YELLOW_TRANSFER
        raise ParseError("Could not infer Vaquita receipt variant from OCR.")

    def _parse_yellow_transfer(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount(lines, ocr.text)
        status, raw_status = self._parse_status(ocr.text, lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=[],
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=None,
            recipient=self._parse_recipient(lines),
            concept=self._parse_concept(lines),
            payment_network=None,
            country_code=country_code,
        )

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text)
        if "gs" in norm or "guarani" in norm or "pyg" in norm:
            return "PYG"
        return "PYG"

    def _parse_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        monto_raw = _field_from_lines(lines, "monto")
        if monto_raw:
            amount = _gs_amount_in_line(monto_raw)
            if amount is not None:
                return amount
        for line in lines:
            if "monto" in normalize_label(line):
                amount = _gs_amount_in_line(line)
                if amount is not None:
                    return amount
        match = re.search(r"Gs\.?\s*([\d.]+)", full_text, flags=re.I)
        if match:
            return parse_decimal_amount(match.group(1))
        return None

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        fecha_raw = _field_from_lines(lines, "fecha")
        if fecha_raw:
            parsed = _parse_spanish_full_month_datetime(fecha_raw)
            if parsed is not None:
                return parsed
            parsed = parse_occurred_at(fecha_raw)
            if parsed is not None:
                return parsed
        for line in lines:
            if "fecha" in normalize_label(line):
                chunk = line.split(":", 1)[-1] if ":" in line else line
                parsed = _parse_spanish_full_month_datetime(chunk)
                if parsed is not None:
                    return parsed
        return _parse_spanish_full_month_datetime(full_text)

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        name = _field_from_lines(lines, "enviado", "a")
        if name is None:
            name = _field_from_lines(lines, "enviado a")
        if name:
            name = natural_name_from_single_comma(name.strip())
        bank = _field_from_lines(lines, "entidad")
        account_raw = _field_from_lines(lines, "cta")
        account: str | None = None
        if account_raw:
            digits = re.sub(r"\D", "", account_raw)
            account = digits if _ACCOUNT_DIGITS.fullmatch(digits) else account_raw.strip()
        document_identifier = _document_from_lines(lines)
        if not name and not bank and not account and not document_identifier:
            return None
        return Party(
            name=name,
            bank=bank,
            account=account,
            document_identifier=document_identifier,
        )

    def _parse_concept(self, lines: list[str]) -> str | None:
        raw = _field_from_lines(lines, "motivo")
        if not raw:
            return None
        cleaned = raw.strip()
        return cleaned or None

    def _parse_status(
        self,
        full_text: str,
        lines: list[str],
    ) -> tuple[TransferStatus, str | None]:
        norm = normalize_label(full_text)
        if "en proceso" in norm:
            raw = self._pending_status_text(lines)
            return TransferStatus.PENDING, raw
        return TransferStatus.UNKNOWN, None

    def _pending_status_text(self, lines: list[str]) -> str | None:
        start = find_line_index(lines, "importante")
        if start is not None:
            for line in lines[start + 1 : start + 4]:
                stripped = line.strip()
                if not stripped:
                    continue
                norm = normalize_label(stripped)
                if "en proceso" in norm:
                    return stripped
                if norm.startswith("la transferencia"):
                    return stripped
        return "La transferencia está en proceso"
