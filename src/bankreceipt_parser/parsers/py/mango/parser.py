"""Mango wallet transfer receipt parsers."""

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
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.mango.variants import MangoVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_GS_LINE = re.compile(r"Gs\.?\s*([\d.]+)", re.I)
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
_MANGO_DATETIME = re.compile(
    r"(?:fecha\s+y\s+hora\s+)?"
    r"([0-9oOIl]{1,2})\s+([a-z]{3})\.?\s+(\d{4})\s*-\s*(\d{1,2}):(\d{2})\s*h",
    re.I,
)
_BANK_ENTITY = re.compile(
    r"([A-Z][A-Z0-9\s.]+BANCO[A-Z0-9\s.]+)",
    re.I,
)
_CTA_VALUE = re.compile(r"cta\.?\s*n[°º*+]?\s*(.+)", re.I)
_TRANS_VALUE = re.compile(r"transacci[oó]n\s*n[°º*]?\s*(.+)", re.I)
_ESTADO_VALUE = re.compile(r"estado\s+(.+)", re.I)


def _ocr_digit_char(ch: str) -> str:
    if ch in "oO":
        return "0"
    if ch in "lI":
        return "1"
    return ch


def _fix_ocr_day(day_raw: str) -> int | None:
    fixed = "".join(_ocr_digit_char(c) for c in day_raw)
    if not fixed.isdigit():
        return None
    day = int(fixed)
    if 1 <= day <= 31:
        return day
    return None


def _amount_from_lines(lines: list[str]) -> Decimal | None:
    for line in lines:
        match = _GS_LINE.search(line)
        if match:
            amount = parse_decimal_amount(match.group(1))
            if amount is not None:
                return amount
        match = _GROUPED_AMOUNT.search(line)
        if match:
            amount = parse_decimal_amount(match.group(0))
            if amount is not None:
                return amount
    return None


def _origen_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if normalize_label(line).startswith("origen"):
            return index
    return find_line_index(lines, "origen")


def _amount_region_end(lines: list[str], variant: str) -> int:
    if variant == MangoVariant.SIP_DETAIL:
        enviaste = find_line_index(lines, "enviaste")
        if enviaste is not None:
            return enviaste + 1
    monto = find_line_index(lines, "monto")
    if monto is not None:
        return monto + 1
    return 0


def _strip_logo_token_prefix(line: str) -> str:
    """Drop a leading OCR token when the rest still looks like a personal name."""
    stripped = line.strip()
    parts = stripped.split(None, 1)
    if len(parts) < 2:
        return stripped
    head, tail = parts
    if len(head) <= 6 and head.isalpha() and re.search(r"[A-Za-z]{3,}", tail):
        return tail.strip()
    return stripped


def _is_recipient_name_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) <= 2:
        return False
    norm = normalize_label(stripped)
    if norm.startswith("origen"):
        return False
    if any(token in norm for token in ("cta", "banco", "gs", "monto", "enviaste", "detalle")):
        return False
    if _BANK_ENTITY.search(stripped):
        return False
    if _GS_LINE.search(stripped) or _GROUPED_AMOUNT.search(stripped):
        return False
    return bool(re.search(r"[A-Za-z]{2,}", stripped))


def _clean_bank_label(label: str) -> str:
    cleaned = re.sub(r"^[a-z]{2,4}\s+", "", label.strip(), flags=re.I)
    cleaned = re.sub(r"^banco\s+", "", cleaned, flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip()


def _recipient_bank_from_line(line: str) -> str | None:
    norm = normalize_label(line)
    if "tu financiera" in norm:
        return None
    match = _BANK_ENTITY.search(line)
    if match:
        return _clean_bank_label(match.group(1))
    if "banco" in norm or "s.a" in norm:
        return _clean_bank_label(line) or None
    return None


def _recipient_account_from_line(line: str) -> str | None:
    match = _CTA_VALUE.search(line)
    if not match:
        return None
    raw = match.group(1).strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 6:
        return digits
    return None


def _sender_masked_account(raw: str) -> str | None:
    stripped = raw.strip()
    if not stripped:
        return None
    plus_digits = re.fullmatch(r"\++(\d{3,6})", stripped)
    if plus_digits:
        return f".....{plus_digits.group(1)}"
    if re.fullmatch(r"[\.*+•]+(\d{0,6})?", stripped):
        return stripped.replace("+", ".")
    if re.search(r"[•*]", stripped):
        return stripped
    return None


def _parse_mango_datetime(text: str) -> datetime | None:
    match = _MANGO_DATETIME.search(text)
    if not match:
        return None
    day_raw, month_s, year_s, hour_s, minute_s = match.groups()
    day = _fix_ocr_day(day_raw)
    month = _SPANISH_MONTHS.get(month_s.casefold()[:3])
    if day is None or month is None:
        return None
    try:
        return datetime(int(year_s), month, day, int(hour_s), int(minute_s))
    except ValueError:
        return None


def _parse_status(lines: list[str]) -> tuple[TransferStatus, str | None]:
    for line in lines:
        match = _ESTADO_VALUE.search(line)
        if not match:
            continue
        raw = match.group(1).strip()
        norm = normalize_label(raw)
        if "procesando" in norm:
            return TransferStatus.PENDING, raw
        if "enviada" in norm or "realizada" in norm or "exitosa" in norm:
            return TransferStatus.COMPLETED, raw
        return TransferStatus.UNKNOWN, raw
    return TransferStatus.UNKNOWN, None


def _parse_transaction_id(lines: list[str]) -> list[TransactionIdentifier]:
    for line in lines:
        match = _TRANS_VALUE.search(normalize_label(line))
        if not match:
            continue
        value = match.group(1).strip()
        if not value:
            continue
        return [
            TransactionIdentifier(
                kind=TransactionIdentifierKind.OPERATION,
                value=value,
                label="Transacción N°",
            )
        ]
    return []


class MangoReceiptParser:
    """Parse Mango wallet transfer receipts."""

    issuer = Issuer.MANGO
    supported_variants = frozenset(variant.value for variant in MangoVariant)

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
        amount = _amount_from_lines(lines)
        status, raw_status = _parse_status(lines)
        payment_network = payment_network_from_text(ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=_parse_transaction_id(lines),
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency="PYG" if amount is not None else None,
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines, selected),
            concept=None,
            payment_network=payment_network,
            country_code=country_code,
        )

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Mango receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia" in norm and re.search(r"\bsip\b", norm):
            return MangoVariant.SIP_DETAIL
        if "detalle" in norm and "enviaste" in norm and "tu financiera" in norm:
            return MangoVariant.SIP_DETAIL
        if find_line_index(lines, "monto") is not None and "detalle" not in norm:
            return MangoVariant.TRANSFER_RECEIPT
        if "mango" in norm and "origen" in norm:
            return MangoVariant.TRANSFER_RECEIPT
        raise ParseError("Could not infer Mango receipt variant from OCR.")

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        for line in lines:
            parsed = _parse_mango_datetime(line)
            if parsed is not None:
                return parsed
        return _parse_mango_datetime(full_text)

    def _parse_sender(self, lines: list[str]) -> Party | None:
        origen_index = _origen_line_index(lines)
        if origen_index is None:
            return None
        line = lines[origen_index]
        name: str | None = None
        match = re.search(r"origen\s+(.+)", line, flags=re.I)
        if match:
            name = match.group(1).strip() or None
        bank: str | None = None
        masked_account: str | None = None
        for follow in lines[origen_index + 1 : origen_index + 4]:
            norm = normalize_label(follow)
            if "fecha" in norm or "transaccion" in norm or "estado" in norm:
                break
            if "tu financiera" in norm:
                continue
            cta_match = _CTA_VALUE.search(follow)
            if cta_match:
                masked_account = _sender_masked_account(cta_match.group(1)) or masked_account
        if not name and not masked_account and bank is None:
            return None
        return Party(name=name, bank=bank, masked_account=masked_account)

    def _parse_recipient(self, lines: list[str], variant: str) -> Party | None:
        origen_index = _origen_line_index(lines)
        if origen_index is None:
            return None
        start = _amount_region_end(lines, variant)
        bank: str | None = None
        account: str | None = None
        name_parts: list[str] = []
        for line in lines[start:origen_index]:
            bank = bank or _recipient_bank_from_line(line)
            account = account or _recipient_account_from_line(line)
            if _is_recipient_name_line(line):
                name_parts.append(_strip_logo_token_prefix(line))
        name = " ".join(name_parts).strip() or None
        if name:
            name = re.sub(r"\s+", " ", name)
        if not name and not bank and not account:
            return None
        return Party(name=name, bank=bank, account=account)
