"""ZETA Banco transfer comprobante parser."""

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
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.zeta.variants import ZetaVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_ACCOUNT_DIGITS = re.compile(r"^\d{5,18}$")


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    match = _GROUPED_AMOUNT.search(line)
    if match:
        return parse_decimal_amount(match.group(0))
    return None


def _section_heading_index(lines: list[str], heading: str) -> int | None:
    target = normalize_label(heading)
    for index, line in enumerate(lines):
        if normalize_label(line) == target:
            return index
    return find_line_index(lines, heading)


def _account_after_label(lines: list[str], start: int, *, stop: int) -> str | None:
    cuenta_index = None
    for index in range(start, stop):
        norm = normalize_label(lines[index])
        if "cuenta" in norm and ("nro" in norm or "de" in norm or norm == "cuenta"):
            cuenta_index = index
            break
    if cuenta_index is None:
        return None
    for follow in lines[cuenta_index + 1 : min(cuenta_index + 4, stop)]:
        candidate = follow.strip()
        if _ACCOUNT_DIGITS.fullmatch(candidate):
            return candidate
    return None


def _party_in_section(lines: list[str], start: int, stop: int) -> Party | None:
    entidad_index = None
    for index in range(start, stop):
        if normalize_label(lines[index]) == "entidad":
            entidad_index = index
            break
    name_end = entidad_index if entidad_index is not None else stop
    raw_name = collect_name_block(lines, start + 1, max_lines=max(1, name_end - start - 1))
    name = natural_name_from_single_comma(raw_name) if raw_name else None
    bank: str | None = None
    if entidad_index is not None:
        for follow in lines[entidad_index + 1 : min(entidad_index + 3, stop)]:
            follow_norm = normalize_label(follow)
            if follow_norm.startswith("nro"):
                break
            if follow.strip():
                bank = follow.strip()
                break
    account = _account_after_label(lines, start, stop=stop)
    if not name and not bank and not account:
        return None
    return Party(name=name, bank=bank, account=account)


class ZetaReceiptParser:
    """Parse ZETA Banco transfer comprobantes from OCR."""

    issuer = Issuer.ZETA
    supported_variants = frozenset(variant.value for variant in ZetaVariant)

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
        if selected != ZetaVariant.TRANSFER_RECEIPT:
            raise ParseError(f"Unsupported ZETA receipt variant: {selected!r}.")
        return self._parse_transfer_receipt(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported ZETA receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if (
            "transferencia" in norm
            and "enviada" in norm
            and "comprobante" in norm
            and _section_heading_index(lines, "para") is not None
            and _section_heading_index(lines, "desde") is not None
        ):
            return ZetaVariant.TRANSFER_RECEIPT
        raise ParseError("Could not infer ZETA receipt variant from OCR.")

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
            raw_status="TRANSFERENCIA ENVIADA",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
            concept=self._parse_concept(lines),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        concept_index = _section_heading_index(lines, "concepto")
        comprobante_index = find_line_index(lines, "comprobante")
        search_end = concept_index if concept_index is not None else len(lines)
        search_start = comprobante_index if comprobante_index is not None else 0
        for line in lines[search_start:search_end]:
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
        if "gs" in norm or "guarani" in norm:
            return "PYG"
        return "PYG"

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        for line in lines:
            parsed = parse_occurred_at(line)
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        for line in lines:
            norm = normalize_label(line)
            if "comprobante" not in norm or "nro" not in norm:
                continue
            inline = value_on_same_line(line, "comprobante")
            if inline:
                digits = re.sub(r"\D", "", inline) or inline.strip()
                if digits:
                    return [
                        TransactionIdentifier(
                            kind=TransactionIdentifierKind.OPERATION,
                            value=digits,
                            label="Nro. Comprobante",
                        )
                    ]
        return []

    def _parse_concept(self, lines: list[str]) -> str | None:
        concept_index = _section_heading_index(lines, "concepto")
        if concept_index is None:
            return None
        parts: list[str] = []
        para_index = _section_heading_index(lines, "para")
        stop = para_index if para_index is not None else len(lines)
        for line in lines[concept_index + 1 : stop]:
            norm = normalize_label(line)
            if not line.strip():
                continue
            if parse_occurred_at(line) is not None:
                break
            if norm.startswith("para"):
                break
            parts.append(line.strip())
        joined = " ".join(parts).strip()
        return joined or None

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        para_index = _section_heading_index(lines, "para")
        desde_index = _section_heading_index(lines, "desde")
        if para_index is None or desde_index is None or desde_index <= para_index:
            return None
        return _party_in_section(lines, para_index, desde_index)

    def _parse_sender(self, lines: list[str]) -> Party | None:
        desde_index = _section_heading_index(lines, "desde")
        if desde_index is None:
            return None
        footer_index = find_line_index(lines, "este comprobante")
        stop = footer_index if footer_index is not None else len(lines)
        return _party_in_section(lines, desde_index, stop)
