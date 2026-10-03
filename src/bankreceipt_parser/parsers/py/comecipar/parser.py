"""COMECIPAR mobile transfer-success screen parser."""

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
from bankreceipt_parser.parsers.common.lines import lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.py.comecipar.variants import ComeciparVariant

_COOMECIPAR_BRAND = re.compile(r"coomecipar|comecipar", re.I)
_AVATAR_PREFIX = re.compile(r"^[A-Za-zÁÉÍÓÚÑ]{1,3}\s+")
_INSTITUTION_TRAILING_ACCOUNT = re.compile(
    r"^(?P<bank>.+?)\s*(?:[·\-–]|\.)\s*(?P<account>\d{6,14})\s*$",
)
_TICKET_LINE = re.compile(r"^\d+\s*:\s*(\d{6,12})\s*$")


def _strip_avatar_prefix(line: str) -> str:
    return _AVATAR_PREFIX.sub("", line.strip(), count=1).strip()


def _trim_trailing_separators(text: str) -> str:
    return re.sub(r"[\s·\-–]+$", "", text.strip())


def _amount_below_gs_label(lines: list[str]) -> Decimal | None:
    for index, line in enumerate(lines):
        token = normalize_label(line).replace(".", "")
        if token != "gs":
            continue
        for nearby in lines[index + 1 : index + 3]:
            amount = parse_decimal_amount(nearby)
            if amount is not None:
                return amount
    return None


def _split_bank_and_account(line: str) -> tuple[str | None, str | None]:
    cleaned = _strip_avatar_prefix(_trim_trailing_separators(line))
    match = _INSTITUTION_TRAILING_ACCOUNT.match(cleaned)
    if match:
        return match.group("bank").strip() or None, match.group("account")
    trailing = re.search(r"(\d{6,14})\s*$", cleaned)
    if trailing:
        bank = _trim_trailing_separators(cleaned[: trailing.start()]) or None
        return bank, trailing.group(1)
    bank_only = _trim_trailing_separators(cleaned) or None
    return bank_only, None


def _find_coomecipar_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _COOMECIPAR_BRAND.search(line):
            return index
    return None


class ComeciparReceiptParser:
    """Parse COMECIPAR transfer-success screens from OCR text."""

    issuer = Issuer.COMECIPAR
    supported_variants = frozenset(variant.value for variant in ComeciparVariant)

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
        if selected != ComeciparVariant.TRANSFER_SUCCESS:
            raise ParseError(f"Unsupported COMECIPAR receipt variant: {selected!r}.")
        return self._parse_transfer_success(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported COMECIPAR receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia exitosa" not in norm:
            raise ParseError("Could not infer COMECIPAR receipt variant from OCR.")
        if _find_coomecipar_line_index(lines) is None and not _COOMECIPAR_BRAND.search(full_text):
            raise ParseError("Could not infer COMECIPAR receipt variant from OCR.")
        return ComeciparVariant.TRANSFER_SUCCESS

    def _parse_transfer_success(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = _amount_below_gs_label(lines) or extract_gs_amount(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(lines),
            status=TransferStatus.COMPLETED,
            raw_status="Transferencia exitosa",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
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

    def _parse_occurred_at(self, full_text: str) -> datetime | None:
        return parse_occurred_at(full_text)

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        for line in lines:
            match = _TICKET_LINE.match(line.strip())
            if match:
                return [
                    TransactionIdentifier(
                        kind=TransactionIdentifierKind.TICKET,
                        value=match.group(1),
                        label="Comprobante",
                    )
                ]
        return []

    def _parse_sender(self, lines: list[str]) -> Party | None:
        coop_index = _find_coomecipar_line_index(lines)
        if coop_index is None:
            return None
        bank, account = _split_bank_and_account(lines[coop_index])
        name: str | None = None
        if coop_index > 0:
            candidate = _strip_avatar_prefix(lines[coop_index - 1])
            if candidate and "transferencia" not in normalize_label(candidate):
                name = candidate
        if not name and not account and not bank:
            return None
        return Party(name=name, account=account, bank=bank)

    def _parse_recipient(self, lines: list[str]) -> Party | None:
        coop_index = _find_coomecipar_line_index(lines)
        if coop_index is None or coop_index + 2 >= len(lines):
            return None
        name = _strip_avatar_prefix(lines[coop_index + 1])
        institution_index = coop_index + 2
        bank, account_on_line = _split_bank_and_account(lines[institution_index])
        account = account_on_line
        if institution_index + 1 < len(lines):
            next_line = lines[institution_index + 1].strip()
            if re.fullmatch(r"\d{6,14}", next_line):
                account = next_line
        if not name and not bank and not account:
            return None
        return Party(name=name, account=account, bank=bank)
