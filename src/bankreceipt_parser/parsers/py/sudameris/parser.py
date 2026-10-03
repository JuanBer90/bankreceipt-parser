"""Sudameris transfer receipt parsers."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifier, TransactionIdentifierKind
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.models.party import Party
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.ocr.structure import OCRResult
from bankreceipt_parser.parsers.common.account_type import account_type_from_text
from bankreceipt_parser.parsers.common.amounts import parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.sudameris.variants import SudamerisVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_RECIPIENT_ACCOUNT_BANK = re.compile(r"^(\d{6,18})\s+(.+)$")
_MASKED_ACCOUNT = re.compile(r"([.*•]+[\d/*•]+)")


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
        norm = normalize_label(line)
        if norm == target or norm.startswith(target):
            return index
    return find_line_index(lines, heading)


def _parse_status(full_text: str) -> tuple[TransferStatus, str | None]:
    norm = normalize_label(full_text)
    if "transferencia exitosa" in norm:
        return TransferStatus.COMPLETED, "¡Transferencia exitosa!"
    if "transferencia bancaria" in norm:
        return TransferStatus.COMPLETED, None
    return TransferStatus.UNKNOWN, None


def _masked_account_from_line(line: str) -> str | None:
    match = _MASKED_ACCOUNT.search(line)
    if match:
        return match.group(1).strip()
    return None


def _account_type_from_line(line: str) -> AccountType:
    return account_type_from_text(line)


class SudamerisReceiptParser:
    """Parse Sudameris SIP transfer receipts from OCR."""

    issuer = Issuer.SUDAMERIS
    supported_variants = frozenset(variant.value for variant in SudamerisVariant)

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
        if selected == SudamerisVariant.TRANSFER_RECEIPT:
            return self._parse_transfer_receipt(ocr, lines, country_code=country_code)
        raise ParseError(f"Unsupported Sudameris receipt variant: {selected!r}.")

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Sudameris receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia bancaria" in norm and _section_index(lines, "enviado por") is not None:
            return SudamerisVariant.TRANSFER_RECEIPT
        if "sudameris" in norm and _section_index(lines, "enviado a") is not None:
            return SudamerisVariant.TRANSFER_RECEIPT
        raise ParseError("Could not infer Sudameris receipt variant from OCR.")

    def _parse_transfer_receipt(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount(lines)
        status, raw_status = _parse_status(ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(lines),
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

    def _parse_amount(self, lines: list[str]) -> Decimal | None:
        heading = _section_index(lines, "transferencia bancaria")
        search_from = heading if heading is not None else 0
        for line in lines[search_from : search_from + 5]:
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        for line in lines:
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        return None

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text)
        if "gs" in norm or "guarani" in norm or "pyg" in norm:
            return "PYG"
        return "PYG"

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        fecha_index = _section_index(lines, "fecha")
        if fecha_index is not None:
            for line in lines[fecha_index : fecha_index + 3]:
                parsed = parse_occurred_at(line)
                if parsed is not None:
                    return parsed
        enviado_a = _section_index(lines, "enviado a")
        soporte = _section_index(lines, "numero de soporte")
        start = (enviado_a or 0) + 1
        end = soporte if soporte is not None else len(lines)
        for line in lines[start:end]:
            norm = normalize_label(line)
            if "numero de soporte" in norm or "enviado" in norm:
                continue
            parsed = parse_occurred_at(line)
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        index = _section_index(lines, "numero de soporte")
        if index is None:
            return []
        for line in lines[index : index + 3]:
            norm = normalize_label(line)
            if "numero de soporte" in norm:
                digits = re.search(r"(\d{6,12})", line)
                if digits:
                    return [
                        TransactionIdentifier(
                            kind=TransactionIdentifierKind.OPERATION,
                            value=digits.group(1),
                            label="Número de Soporte",
                        )
                    ]
                continue
            stripped = line.strip()
            if re.fullmatch(r"\d{6,12}", stripped):
                return [
                    TransactionIdentifier(
                        kind=TransactionIdentifierKind.OPERATION,
                        value=stripped,
                        label="Número de Soporte",
                    )
                ]
        return []

    def _parse_sender(self, lines: list[str]) -> Party | None:
        start = _section_index(lines, "enviado por")
        end = _section_index(lines, "enviado a")
        if start is None:
            return None
        boundary = end if end is not None and end > start else start + 4
        name: str | None = None
        masked_account: str | None = None
        account_type = AccountType.UNKNOWN
        for line in lines[start + 1 : boundary]:
            stripped = line.strip()
            if not stripped:
                continue
            norm = normalize_label(stripped)
            if "enviado" in norm:
                break
            if masked_account is None:
                masked = _masked_account_from_line(stripped)
                if masked:
                    masked_account = masked
                    account_type = _account_type_from_line(stripped)
                    continue
            if (
                name is None
                and not _gs_amount_in_line(stripped)
                and re.search(r"[A-Za-z]{2,}", stripped)
                and "caja" not in norm
            ):
                name = natural_name_from_single_comma(stripped)
        if not name and not masked_account:
            return None
        return Party(name=name, masked_account=masked_account, account_type=account_type)

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        start = _section_index(lines, "enviado a")
        if start is None:
            return None
        fecha = _section_index(lines, "fecha")
        soporte = _section_index(lines, "numero de soporte")
        end = min(
            index for index in (fecha, soporte, len(lines)) if index is not None and index > start
        )
        name: str | None = None
        account: str | None = None
        bank: str | None = None
        for line in lines[start + 1 : end]:
            stripped = line.strip()
            if not stripped:
                continue
            norm = normalize_label(stripped)
            if "fecha" in norm or "numero de soporte" in norm:
                break
            if parse_occurred_at(stripped) is not None and name is not None:
                break
            match = _RECIPIENT_ACCOUNT_BANK.match(stripped)
            if match:
                account = match.group(1)
                bank = match.group(2).strip() or None
                continue
            if name is None and re.search(r"[A-Za-z]{2,}", stripped):
                name = stripped
        if not name and not account and not bank:
            return None
        return Party(name=name, account=account, bank=bank)
