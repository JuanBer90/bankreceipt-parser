"""EKO wallet transfer receipt parsers."""

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
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.eko.variants import EkoVariant

_GROUPED_AMOUNT = re.compile(r"\d{1,3}(?:\.\d{3})+")
_SPANISH_MONTH = re.compile(
    r"(\d{1,2})\s+([a-z]{3})\.?\s+(\d{4})",
    re.I,
)


def _first_grouped_amount(line: str) -> Decimal | None:
    match = _GROUPED_AMOUNT.search(line)
    if not match:
        return None
    return parse_decimal_amount(match.group(0))


def _amount_after_heading(lines: list[str], heading: str, window: int = 6) -> Decimal | None:
    index = find_line_index(lines, heading)
    if index is None:
        return None
    for line in lines[index : index + window]:
        amount = _first_grouped_amount(line)
        if amount is not None:
            return amount
    return None


def _masked_account_from_cta_line(line: str) -> str | None:
    if "cta" not in normalize_label(line) and "n°" not in normalize_label(line):
        return None
    if not re.search(r"[•*]", line):
        return None
    match = re.search(r"([•*]+)\s*(\d{0,6})\s*$", line)
    if not match:
        return None
    mask, suffix = match.groups()
    return f"{mask}{suffix}".strip() if suffix else mask.strip()


def _parse_spanish_month_datetime(text: str) -> datetime | None:
    match = _SPANISH_MONTH.search(text)
    if not match:
        return None
    day_s, month_s, year_s = match.groups()
    months = {
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
    month = months.get(month_s.casefold()[:3])
    if month is None:
        return None
    return parse_occurred_at(f"{day_s}/{month:02d}/{year_s} 00:00")


class EkoReceiptParser:
    """Parse EKO wallet transfer receipts."""

    issuer = Issuer.EKO
    supported_variants = frozenset(variant.value for variant in EkoVariant)

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
        if selected == EkoVariant.SEND_RECEIPT:
            return self._parse_send_receipt(ocr, lines, country_code=country_code)
        if selected == EkoVariant.TRANSFER_DETAIL:
            return self._parse_transfer_detail(ocr, lines, country_code=country_code)
        raise ParseError(f"Unsupported EKO receipt variant: {selected!r}.")

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported EKO receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "detalle" in norm and "enviaste" in norm and "transferencia" in norm:
            return EkoVariant.TRANSFER_DETAIL
        if "listo" in norm and "envio" in norm:
            return EkoVariant.SEND_RECEIPT
        raise ParseError("Could not infer EKO receipt variant from OCR.")

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        norm = normalize_label(full_text)
        if "gs" in norm or "guarani" in norm or "¢" in full_text or "₲" in full_text:
            return "PYG"
        if amount is not None and _GROUPED_AMOUNT.search(full_text):
            return "PYG"
        return None

    def _parse_send_receipt(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = _amount_after_heading(lines, "envio")
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=[],
            status=TransferStatus.COMPLETED,
            raw_status="Listo",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_send_receipt_datetime(ocr.text),
            sender=self._parse_send_receipt_sender(lines),
            recipient=self._parse_send_receipt_recipient(lines),
            concept=self._parse_send_receipt_note(lines),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_transfer_detail(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = _amount_after_heading(lines, "transferencia", window=8)
        if amount is None:
            amount = _amount_after_heading(lines, "enviaste", window=4)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_transfer_detail_identifiers(lines),
            status=TransferStatus.COMPLETED,
            raw_status=None,
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_transfer_detail_datetime(lines, ocr.text),
            sender=None,
            recipient=self._parse_transfer_detail_recipient(lines),
            concept=None,
            payment_network=None,
            country_code=country_code,
        )

    def _parse_send_receipt_datetime(self, full_text: str) -> datetime | None:
        return parse_occurred_at(full_text)

    def _parse_send_receipt_sender(self, lines: list[str]) -> Party | None:
        familiar_index = find_line_index(lines, "banco familiar")
        if familiar_index is None:
            familiar_index = find_line_index(lines, "familiar")
        if familiar_index is None:
            return None
        bank = "Banco Familiar" if "banco" in normalize_label(lines[familiar_index]) else None
        masked_account: str | None = None
        for line in lines[familiar_index : familiar_index + 3]:
            masked_account = _masked_account_from_cta_line(line) or masked_account
        envio_index = find_line_index(lines, "envio")
        start = (envio_index + 1) if envio_index is not None else 0
        name_parts: list[str] = []
        for line in lines[start:familiar_index]:
            norm = normalize_label(line)
            if _first_grouped_amount(line) is not None:
                continue
            if "banco" in norm or "cta" in norm:
                continue
            stripped = line.strip()
            if len(stripped) < 3 or re.fullmatch(r"[a-zA-Z]", stripped):
                continue
            cleaned = re.sub(r"^[A-Za-z0-9]{1,3}\)\s*", "", stripped)
            cleaned = re.sub(r"\s+ann$", "", cleaned, flags=re.I).strip()
            if cleaned and not cleaned.isdigit() and not re.fullmatch(r"y", cleaned, re.I):
                name_parts.append(cleaned)
        name = " ".join(name_parts).strip() or None
        if name:
            name = re.sub(r"^y\s+", "", name, flags=re.I).strip() or None
        if not name and not bank and not masked_account:
            return None
        return Party(name=name, bank=bank, masked_account=masked_account)

    def _parse_send_receipt_recipient(self, lines: list[str]) -> Party | None:
        alias_index = find_line_index(lines, "alias")
        if alias_index is None:
            return None
        alias_match = re.search(r"(\d{5,12})", lines[alias_index])
        alias = alias_match.group(1) if alias_match else None
        name: str | None = None
        for line in reversed(lines[:alias_index]):
            norm = normalize_label(line)
            if "banco" in norm or "cta" in norm or "familiar" in norm:
                continue
            if "alias" in norm or _first_grouped_amount(line) is not None:
                continue
            if len(line.strip()) < 4:
                continue
            name = line.strip()
            break
        if not name and not alias:
            return None
        return Party(name=name, alias=alias)

    def _parse_send_receipt_note(self, lines: list[str]) -> str | None:
        alias_index = find_line_index(lines, "alias")
        if alias_index is None:
            return None
        for line in lines[alias_index + 1 : alias_index + 4]:
            norm = normalize_label(line)
            if "fecha" in norm or "solicitamos" in norm or len(line.strip()) < 4:
                continue
            if re.search(r"[A-Za-z]{3,}", line):
                return line.strip()
        return None

    def _parse_transfer_detail_identifiers(
        self,
        lines: list[str],
    ) -> list[TransactionIdentifier]:
        start = find_line_index(lines, "transferencia")
        end = find_line_index(lines, "compartir") or len(lines)
        if start is None:
            return []
        saw_date = False
        for line in lines[start:end]:
            if _parse_spanish_month_datetime(line):
                saw_date = True
                continue
            if not saw_date:
                continue
            match = re.fullmatch(r"\d{8,14}", line.strip())
            if match:
                return [
                    TransactionIdentifier(
                        kind=TransactionIdentifierKind.TICKET,
                        value=match.group(0),
                        label="Nro. de comprobante",
                    )
                ]
        return []

    def _parse_transfer_detail_datetime(self, lines: list[str], full_text: str) -> datetime | None:
        start = find_line_index(lines, "transferencia")
        end = find_line_index(lines, "compartir") or len(lines)
        if start is not None:
            for line in lines[start:end]:
                parsed = _parse_spanish_month_datetime(line)
                if parsed is not None:
                    return parsed
        return _parse_spanish_month_datetime(full_text)

    def _parse_transfer_detail_recipient(self, lines: list[str]) -> Party | None:
        enviaste_index = find_line_index(lines, "enviaste")
        transferencia_index = find_line_index(lines, "transferencia")
        name: str | None = None
        if enviaste_index is not None:
            parts: list[str] = []
            for line in lines[enviaste_index + 1 : transferencia_index or len(lines)]:
                stripped = re.sub(r"^<=\s*G\s*", "", line.strip())
                stripped = re.sub(r"^=>\s*a\s*", "", stripped, flags=re.I).strip()
                if not stripped or _first_grouped_amount(stripped) is not None:
                    continue
                if len(stripped) <= 2:
                    continue
                parts.append(stripped)
            name = " ".join(parts).strip() or None
        account: str | None = None
        if transferencia_index is not None:
            for line in lines[transferencia_index + 1 : transferencia_index + 8]:
                if _parse_spanish_month_datetime(line):
                    break
                match = re.match(r"^(\d{6,14})\b", line.strip())
                if match:
                    account = match.group(1)
                    break
        if not name and not account:
            return None
        return Party(name=name, account=account)
