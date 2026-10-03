"""Banco Continental (Paraguay) transfer receipt parser."""

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
from bankreceipt_parser.parsers.common.amounts import extract_gs_amount, parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.continental.variants import ContinentalVariant

_FIELD_LABEL_PREFIXES = (
    "comprobante",
    "concepto",
    "monto",
    "nombre",
    "cuenta",
    "entidad",
    "moneda",
    "detalles",
    "destino",
    "origen",
    "envio",
    "envío",
)


def _inline_value_after_label(line: str, label: str) -> str | None:
    """Value on the same line after a label prefix (space-separated, no colon)."""
    if normalize_label(label) not in normalize_label(line):
        return None
    parts = re.split(rf"(?i){re.escape(label)}", line, maxsplit=1)
    if len(parts) < 2:
        return None
    value = parts[1].strip()
    return value or None


def _origen_cuenta_party_fields(raw: str | None) -> tuple[str | None, str | None]:
    """Map Origen ``Cuenta`` on ``transfer_receipt`` to party account fields.

    In this variant, Destino shows a full ``Cuenta`` value and Origen shows a masked
    ``Cuenta`` (asterisks plus a short suffix) on the receipts we have evidence for.
    We never copy Origen OCR digits into ``account``. ``masked_account`` is set only
    when the OCR text still contains mask characters; if OCR drops the asterisks we
    cannot recover the masked value reliably and leave both fields empty.
    """
    if not raw:
        return None, None
    value = raw.strip()
    if not value or "*" not in value:
        return None, None
    return None, re.sub(r"\s+", " ", value)


class ContinentalReceiptParser:
    """Parse Continental transfer receipts from OCR text."""

    issuer = Issuer.CONTINENTAL
    supported_variants = frozenset(variant.value for variant in ContinentalVariant)

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
        if selected != ContinentalVariant.TRANSFER_RECEIPT:
            raise ParseError(f"Unsupported Continental receipt variant: {selected!r}.")
        return self._parse_transfer_receipt(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Continental receipt variant: {variant!r}.")
            return variant
        lines = lines_from_ocr(ocr)
        return self._detect_variant(ocr.text, lines)

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "comprobante de transferencia" not in norm:
            raise ParseError("Could not infer Continental receipt variant from OCR.")
        has_structure = (
            find_line_index(lines, "monto debitado") is not None
            and find_line_index(lines, "destino") is not None
            and find_line_index(lines, "origen") is not None
        )
        if not has_structure:
            raise ParseError("Could not infer Continental receipt variant from OCR.")
        return ContinentalVariant.TRANSFER_RECEIPT

    def _parse_transfer_receipt(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(lines),
            status=TransferStatus.COMPLETED,
            raw_status=None,
            amount=amount,
            currency=self._parse_currency(lines, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
            concept=self._parse_concept(lines),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        ticket = self._field_in_section(lines, "detalles", ("destino",), "comprobante")
        if not ticket:
            return []
        digits = re.sub(r"\D", "", ticket) or ticket.strip()
        return [
            TransactionIdentifier(
                kind=TransactionIdentifierKind.TICKET,
                value=digits,
                label="Comprobante",
            )
        ]

    def _parse_concept(self, lines: list[str]) -> str | None:
        return self._field_in_section(lines, "detalles", ("destino",), "concepto")

    def _parse_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        idx = find_line_index(lines, "monto debitado")
        if idx is not None:
            inline = _inline_value_after_label(lines[idx], "monto debitado")
            if inline:
                parsed = parse_decimal_amount(inline) or _amount_in_text(inline)
                if parsed is not None:
                    return parsed
        return extract_gs_amount(lines, full_text)

    def _parse_currency(self, lines: list[str], amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        moneda = self._field_in_section(lines, "destino", ("origen",), "moneda")
        if moneda and normalize_label(moneda) == "pyg":
            return "PYG"
        for line in lines:
            norm = normalize_label(line)
            has_currency_token = (
                "gs" in norm.replace(".", "") or "guarani" in norm or norm == "pyg"
            )
            if has_currency_token and ("monto" in norm or moneda is not None):
                return "PYG"
        return None

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        detalles_idx = find_line_index(lines, "detalles")
        search_end = detalles_idx if detalles_idx is not None else min(8, len(lines))
        for index in range(0, search_end):
            parsed = parse_occurred_at(lines[index])
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _parse_sender(self, lines: list[str]) -> Party | None:
        name = self._field_in_section(lines, "origen", ("envio", "envío"), "nombre")
        if name:
            name = natural_name_from_single_comma(name)
        account_raw = self._field_in_section(lines, "origen", ("envio", "envío"), "cuenta")
        account, masked_account = _origen_cuenta_party_fields(account_raw)
        if not name and not account and not masked_account:
            return None
        return Party(name=name, account=account, masked_account=masked_account)

    def _parse_recipient(self, lines: list[str]) -> Party:
        return Party(
            name=self._field_in_section(lines, "destino", ("origen",), "nombre"),
            account=self._field_in_section(lines, "destino", ("origen",), "cuenta"),
            bank=self._field_in_section(lines, "destino", ("origen",), "entidad"),
        )

    def _field_in_section(
        self,
        lines: list[str],
        section: str,
        end_markers: tuple[str, ...],
        field_label: str,
    ) -> str | None:
        start = find_line_index(lines, section)
        if start is None:
            return None
        end = len(lines)
        for marker in end_markers:
            idx = find_line_index(lines[start + 1 :], marker)
            if idx is not None:
                end = min(end, start + 1 + idx)
        for line in lines[start + 1 : end]:
            norm = normalize_label(line)
            if norm == normalize_label(section):
                continue
            value = _inline_value_after_label(line, field_label)
            if value and not self._is_field_label(normalize_label(value)):
                return value.strip()
        return None

    def _is_field_label(self, normalized_line: str) -> bool:
        return any(normalized_line.startswith(prefix) for prefix in _FIELD_LABEL_PREFIXES)


def _amount_in_text(text: str) -> Decimal | None:
    match = re.search(r"[\d.]+", text.replace("Gs.", "").replace("Gs", ""))
    if not match:
        return None
    return parse_decimal_amount(match.group(0))
