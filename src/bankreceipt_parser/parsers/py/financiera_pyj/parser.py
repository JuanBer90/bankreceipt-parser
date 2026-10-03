"""FINANCIERA PYJ transfer comprobante parser."""

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
from bankreceipt_parser.parsers.py.financiera_pyj.variants import FinancieraPyjVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_ACCOUNT_DIGITS = re.compile(r"\b(\d{5,18})\b")


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = _GROUPED_AMOUNT.search(line)
    if match:
        return parse_decimal_amount(match.group(0))
    return None


def _label_prefix_pattern(*label_parts: str) -> str:
    if (
        len(label_parts) == 2
        and normalize_label(label_parts[0]) == "nombre"
        and normalize_label(label_parts[1]) == "titular"
    ):
        return r"(?i)nombre\s+del\s+titular"
    return r"(?i)" + r"\s+".join(re.escape(part) for part in label_parts)


def _label_value(line: str, *label_parts: str) -> str | None:
    """Extract a field value after label tokens on the same line (with or without colon)."""
    norm = normalize_label(line)
    needles = tuple(normalize_label(part) for part in label_parts)
    if not all(needle in norm for needle in needles):
        return None
    if ":" in line:
        value = line.split(":", 1)[1].strip()
        return value or None
    match = re.search(_label_prefix_pattern(*label_parts), line)
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


def _meaningful_concept(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if re.fullmatch(r"[\W_]+", cleaned):
        return None
    if len(cleaned) >= 4 and len(set(cleaned.casefold())) <= 2:
        return None
    return cleaned


class FinancieraPyjReceiptParser:
    """Parse FINANCIERA PYJ SIP transfer comprobantes from OCR."""

    issuer = Issuer.FINANCIERA_PYJ
    supported_variants = frozenset(variant.value for variant in FinancieraPyjVariant)

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
        if selected != FinancieraPyjVariant.TRANSFER_RECEIPT:
            raise ParseError(f"Unsupported FINANCIERA PYJ receipt variant: {selected!r}.")
        return self._parse_transfer_receipt(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported FINANCIERA PYJ receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "comprobante de transferencia" not in norm:
            raise ParseError("Could not infer FINANCIERA PYJ receipt variant from OCR.")
        if _field_from_lines(lines, "nombre", "titular") is None and find_line_index(
            lines, "nombre del titular"
        ) is None:
            raise ParseError("Could not infer FINANCIERA PYJ receipt variant from OCR.")
        if find_line_index(lines, "cuenta debito") is None and find_line_index(
            lines, "cuenta débito"
        ) is None:
            raise ParseError("Could not infer FINANCIERA PYJ receipt variant from OCR.")
        return FinancieraPyjVariant.TRANSFER_RECEIPT

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
            raw_status="Comprobante de Transferencia",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
            concept=_meaningful_concept(self._parse_concept(lines)),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        operation = _field_from_lines(lines, "nro", "transaccion")
        if operation:
            digits = re.sub(r"\D", "", operation) or operation.strip()
            if digits:
                identifiers.append(
                    TransactionIdentifier(
                        kind=TransactionIdentifierKind.OPERATION,
                        value=digits,
                        label="Nro. Transacción",
                    )
                )
        reference = _field_from_lines(lines, "ntr")
        if reference:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.REFERENCE,
                    value=reference.strip(),
                    label="NTR",
                )
            )
        return identifiers

    def _parse_concept(self, lines: list[str]) -> str | None:
        return _field_from_lines(lines, "detalle")

    def _parse_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        for line in reversed(lines):
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        match = re.search(r"Gs\.?\s*([\d.]+)", full_text, flags=re.I)
        if match:
            return parse_decimal_amount(match.group(1))
        return None

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text)
        if "gs" in norm or "guarani" in norm or "pyg" in norm:
            return "PYG"
        return "PYG"

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        for line in lines[:4]:
            if "fecha" in normalize_label(line) or "hora" in normalize_label(line):
                parsed = parse_occurred_at(line)
                if parsed is not None:
                    return parsed
        combined = " ".join(lines[:3])
        parsed = parse_occurred_at(combined)
        if parsed is not None:
            return parsed
        return parse_occurred_at(full_text)

    def _parse_sender(self, lines: list[str]) -> Party | None:
        name = _field_from_lines(lines, "nombre", "titular")
        if name:
            name = natural_name_from_single_comma(name.strip())
        account_raw = _field_from_lines(lines, "cuenta", "debito")
        account: str | None = None
        if account_raw:
            match = _ACCOUNT_DIGITS.search(account_raw)
            account = match.group(1) if match else account_raw.strip()
        if not name and not account:
            return None
        return Party(name=name, account=account)

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        name = _field_from_lines(lines, "beneficiario")
        if name:
            name = natural_name_from_single_comma(name.strip())
        account_raw = _field_from_lines(lines, "cuenta", "credito")
        account: str | None = None
        if account_raw:
            match = _ACCOUNT_DIGITS.search(account_raw)
            account = match.group(1) if match else account_raw.strip()
        bank = _field_from_lines(lines, "entidad", "destino")
        if not name and not account and not bank:
            return None
        return Party(name=name, bank=bank, account=account)
