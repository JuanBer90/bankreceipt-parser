"""Banco BASA transfer confirmation parsers."""

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
from bankreceipt_parser.parsers.common.amounts import extract_gs_amount, parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.py.basa.variants import BasaVariant

_AVATAR_PREFIX = re.compile(r"^[A-Za-zÁÉÍÓÚÑ]{1,3}\s+")
_AH_ACCOUNT = re.compile(r"AH-(\d{6,14})", re.I)
_COMPROBANTE_VALUE = re.compile(r"Comprobante:\s*(\d{6,14})", re.I)


def _strip_avatar_prefix(line: str) -> str:
    return _AVATAR_PREFIX.sub("", line.strip(), count=1).strip()


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    return None


def _parse_bank_ah_line(line: str) -> tuple[str | None, str | None, AccountType]:
    account_match = _AH_ACCOUNT.search(line)
    account = account_match.group(1) if account_match else None
    account_type = AccountType.SAVINGS if account_match else AccountType.UNKNOWN
    bank = re.split(r"\s*-\s*", line, maxsplit=1)[0]
    bank = _strip_avatar_prefix(bank).strip()
    bank = re.sub(r"\s*AH-.*$", "", bank, flags=re.I).strip() or None
    return bank, account, account_type


def _find_banco_basa_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if "banco basa" in normalize_label(line):
            return index
    return None


def _is_transfer_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) <= 2:
        return True
    norm = normalize_label(stripped)
    if norm in {"a", "y", "o", "co", "pe", "ef", "ds", "xn", "wl", "ae"}:
        return True
    if stripped.startswith("hace ") or "minutos" in norm:
        return True
    if norm.startswith("responder") or norm == "basa":
        return True
    return bool(re.fullmatch(r"\(\w\)", stripped))


class BasaReceiptParser:
    """Parse BASA transfer success screens from OCR."""

    issuer = Issuer.BASA
    supported_variants = frozenset(variant.value for variant in BasaVariant)

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
        if selected == BasaVariant.TRANSFER_SUCCESS:
            return self._parse_transfer_success(ocr, lines, country_code=country_code)
        if selected == BasaVariant.PARTY_CARDS:
            return self._parse_party_cards(ocr, lines, country_code=country_code)
        raise ParseError(f"Unsupported BASA receipt variant: {selected!r}.")

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported BASA receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia exitosa" not in norm:
            raise ParseError("Could not infer BASA receipt variant from OCR.")
        if "banco basa" in norm and "comprobante" in norm:
            return BasaVariant.PARTY_CARDS
        has_monto = find_line_index(lines, "monto") is not None
        has_fecha = find_line_index(lines, "fecha") is not None
        if has_monto and has_fecha:
            return BasaVariant.TRANSFER_SUCCESS
        raise ParseError("Could not infer BASA receipt variant from OCR.")

    def _parse_transfer_success(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount_labeled(lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=[],
            status=TransferStatus.COMPLETED,
            raw_status="Transferencia exitosa",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at_transfer_success(ocr.text),
            sender=None,
            recipient=self._parse_recipient_transfer_success(lines),
            concept=None,
            payment_network=None,
            country_code=country_code,
        )

    def _parse_party_cards(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_party_cards_amount(lines) or extract_gs_amount(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_party_cards_identifiers(ocr.text),
            status=TransferStatus.COMPLETED,
            raw_status="Transferencia exitosa",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=parse_occurred_at(ocr.text),
            sender=self._parse_sender_party_cards(lines),
            recipient=self._parse_recipient_party_cards(lines),
            concept=None,
            payment_network=None,
            country_code=country_code,
        )

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text).replace(".", "")
        if "gs" in norm or "guarani" in norm:
            return "PYG"
        return None

    def _parse_occurred_at_transfer_success(self, full_text: str) -> datetime | None:
        norm = normalize_label(full_text)
        if "hoy a las" in norm or norm.startswith("hoy "):
            return None
        return parse_occurred_at(full_text)

    def _parse_party_cards_amount(self, lines: list[str]) -> Decimal | None:
        after_success = False
        for line in lines:
            if "transferencia exitosa" in normalize_label(line):
                after_success = True
                continue
            if not after_success:
                continue
            if "comprobante" in normalize_label(line):
                break
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        return None

    def _parse_amount_labeled(self, lines: list[str]) -> Decimal | None:
        monto_index = find_line_index(lines, "monto")
        if monto_index is None:
            return extract_gs_amount(lines, "\n".join(lines))
        for line in lines[monto_index : monto_index + 6]:
            amount = _gs_amount_in_line(line)
            if amount is not None:
                return amount
        return None

    def _parse_recipient_transfer_success(self, lines: list[str]) -> Party | None:
        monto_index = find_line_index(lines, "monto")
        end = monto_index if monto_index is not None else len(lines)
        name: str | None = None
        alias: str | None = None
        bank: str | None = None
        account: str | None = None
        account_type = AccountType.UNKNOWN
        for line in lines[:end]:
            if "transferencia exitosa" in normalize_label(line):
                continue
            if "alias" in normalize_label(line):
                match = re.search(r"(\d{5,12})", line)
                if match:
                    alias = match.group(1)
                continue
            if _AH_ACCOUNT.search(line):
                bank, account, account_type = _parse_bank_ah_line(line)
                continue
            if not _is_transfer_noise(line) and name is None:
                candidate = _strip_avatar_prefix(line)
                if candidate and "alias" not in normalize_label(candidate):
                    name = candidate
        if not name and not account and not bank:
            return None
        return Party(name=name, account=account, bank=bank, account_type=account_type, alias=alias)

    def _parse_party_cards_identifiers(self, full_text: str) -> list[TransactionIdentifier]:
        match = _COMPROBANTE_VALUE.search(full_text)
        if not match:
            return []
        return [
            TransactionIdentifier(
                kind=TransactionIdentifierKind.TICKET,
                value=match.group(1),
                label="Comprobante",
            )
        ]

    def _parse_sender_party_cards(self, lines: list[str]) -> Party | None:
        basa_index = _find_banco_basa_line_index(lines)
        if basa_index is None:
            return None
        bank, account, account_type = _parse_bank_ah_line(lines[basa_index])
        name: str | None = None
        index = basa_index - 1
        while index >= 0:
            line = lines[index]
            if _is_transfer_noise(line) or "transferencia" in normalize_label(line):
                index -= 1
                continue
            candidate = _strip_avatar_prefix(line)
            if candidate:
                name = candidate
                break
            index -= 1
        if not name and not account and not bank:
            return None
        return Party(name=name, account=account, bank=bank, account_type=account_type)

    def _parse_recipient_party_cards(self, lines: list[str]) -> Party | None:
        basa_index = _find_banco_basa_line_index(lines)
        if basa_index is None or basa_index + 2 >= len(lines):
            return None
        name_line = lines[basa_index + 1]
        bank_line = lines[basa_index + 2]
        if _AH_ACCOUNT.search(name_line) and not _AH_ACCOUNT.search(bank_line):
            name_line, bank_line = bank_line, name_line
        name = _strip_avatar_prefix(name_line)
        if "comprobante" in normalize_label(name):
            return None
        bank, account, account_type = _parse_bank_ah_line(bank_line)
        if not name and not bank and not account:
            return None
        return Party(name=name, account=account, bank=bank, account_type=account_type)
