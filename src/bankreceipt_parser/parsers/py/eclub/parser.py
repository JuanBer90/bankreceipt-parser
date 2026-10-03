"""eCLUB transfer confirmation screen parser."""

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
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.eclub.variants import EclubVariant

_SECTION_LABELS = frozenset({"beneficiario", "remitente"})
_FIELD_LABEL_PREFIXES = (
    "monto",
    "estado",
    "fecha",
    "nro",
    "cuenta",
    "entidad",
    "titular",
    "hora",
)


def _inline_value_after_label(line: str, label: str) -> str | None:
    if normalize_label(label) not in normalize_label(line):
        return None
    parts = re.split(rf"(?i){re.escape(label)}", line, maxsplit=1)
    if len(parts) < 2:
        return None
    value = parts[1].strip()
    return value or None


def _section_heading_index(lines: list[str], heading: str) -> int | None:
    target = normalize_label(heading)
    for index, line in enumerate(lines):
        if normalize_label(line) == target:
            return index
    return find_line_index(lines, heading)


def _is_field_label_line(line: str) -> bool:
    norm = normalize_label(line)
    if norm in _SECTION_LABELS:
        return True
    return any(norm.startswith(prefix) for prefix in _FIELD_LABEL_PREFIXES)


def _digits_at_end(line: str) -> str | None:
    match = re.search(r"(\d{6,14})\s*$", line.strip())
    return match.group(1) if match else None


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = re.search(r"(\d{1,3}(?:\.\d{3})+)", line)
    if match and "gs" in normalize_label(line):
        return parse_decimal_amount(match.group(1))
    return None


class EclubReceiptParser:
    """Parse eCLUB transfer screens from OCR."""

    issuer = Issuer.ECLUB
    supported_variants = frozenset(variant.value for variant in EclubVariant)

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
        if selected != EclubVariant.TRANSFER_SCREEN:
            raise ParseError(f"Unsupported ECLUB receipt variant: {selected!r}.")
        return self._parse_transfer_screen(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported ECLUB receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia realizada" not in norm:
            raise ParseError("Could not infer ECLUB receipt variant from OCR.")
        if _section_heading_index(lines, "beneficiario") is None:
            raise ParseError("Could not infer ECLUB receipt variant from OCR.")
        if _section_heading_index(lines, "remitente") is None:
            raise ParseError("Could not infer ECLUB receipt variant from OCR.")
        return EclubVariant.TRANSFER_SCREEN

    def _parse_transfer_screen(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount(lines)
        status, raw_status = self._parse_status(lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=[],
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
            concept=None,
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text).replace(".", "")
        if "gs" in norm or "guarani" in norm:
            return "PYG"
        return None

    def _parse_amount(self, lines: list[str]) -> Decimal | None:
        index = find_line_index(lines, "monto")
        if index is not None:
            amount = _gs_amount_in_line(lines[index])
            if amount is not None:
                return amount
        for line in lines:
            if normalize_label(line).startswith("monto"):
                amount = _gs_amount_in_line(line)
                if amount is not None:
                    return amount
        return None

    def _parse_status(self, lines: list[str]) -> tuple[TransferStatus, str | None]:
        index = find_line_index(lines, "estado")
        if index is None:
            return TransferStatus.UNKNOWN, None
        for candidate in (lines[index], lines[index + 1] if index + 1 < len(lines) else ""):
            if not candidate:
                continue
            inline = _inline_value_after_label(candidate, "estado")
            for token in (inline, candidate):
                if not token:
                    continue
                norm = normalize_label(token)
                if "pendiente" in norm:
                    return TransferStatus.PENDING, "Pendiente"
                if "complet" in norm or "aprob" in norm:
                    return TransferStatus.COMPLETED, token.strip()
        return TransferStatus.UNKNOWN, None

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        index = find_line_index(lines, "fecha")
        if index is not None:
            chunk = lines[index]
            if index + 1 < len(lines) and re.search(r"\d{2}/\d{2}/\d{4}", lines[index + 1]):
                chunk = f"{chunk} {lines[index + 1]}"
            parsed = parse_occurred_at(chunk)
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        start = _section_heading_index(lines, "beneficiario")
        end = _section_heading_index(lines, "remitente")
        if start is None or end is None or end <= start:
            return None
        account: str | None = None
        bank: str | None = None
        name: str | None = None
        for line in lines[start + 1 : end]:
            norm = normalize_label(line)
            if "nro" in norm and "cuenta" in norm:
                account = _digits_at_end(line) or _inline_value_after_label(line, "cuenta")
                continue
            if norm.startswith("entidad"):
                bank = _inline_value_after_label(line, "entidad")
                continue
            if norm.startswith("titular"):
                name = _inline_value_after_label(line, "titular")
                continue
            if name and not _is_field_label_line(line):
                name = f"{name} {line.strip()}".strip()
        if not name and not bank and not account:
            return None
        return Party(name=name, account=account, bank=bank)

    def _parse_sender(self, lines: list[str]) -> Party | None:
        start = _section_heading_index(lines, "remitente")
        if start is None:
            return None
        name: str | None = None
        account: str | None = None
        for line in lines[start + 1 :]:
            norm = normalize_label(line)
            if norm.startswith("titular"):
                name = _inline_value_after_label(line, "titular")
                continue
            if norm.startswith("cuenta") and "nro" not in norm:
                account = _digits_at_end(line) or _inline_value_after_label(line, "cuenta")
                break
            if name and not _is_field_label_line(line):
                name = f"{name} {line.strip()}".strip()
        if not name and not account:
            return None
        return Party(name=name, account=account)
