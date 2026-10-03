"""Banco Atlas (Paraguay) transfer receipt parser."""

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
from bankreceipt_parser.parsers.common.amounts import extract_gs_amount, parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import (
    collect_name_block,
    find_line_index,
    lines_from_ocr,
    normalize_label,
    value_on_same_line,
)
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.atlas.variants import AtlasVariant

_FIELD_LABEL_PREFIXES = (
    "destinatario",
    "beneficiario",
    "cuenta",
    "entidad",
    "monto",
    "fecha",
    "nro",
    "ref",
    "remitente",
    "informacion",
)


def _sanitize_operation_id(raw: str) -> str:
    cleaned = re.sub(r"^[\s.:]+", "", raw.strip())
    digits = re.sub(r"\D", "", cleaned)
    return digits if digits else cleaned


def _amount_in_text(text: str) -> Decimal | None:
    match = re.search(r"[\d.]+", text.replace("Gs.", "").replace("Gs", ""))
    if not match:
        return None
    return parse_decimal_amount(match.group(0))


class AtlasReceiptParser:
    """Parse Atlas transfer receipts from OCR text."""

    issuer = Issuer.ATLAS
    supported_variants = frozenset(variant.value for variant in AtlasVariant)

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
        if selected != AtlasVariant.TRANSFER_RECEIPT:
            raise ParseError(f"Unsupported Atlas receipt variant: {selected!r}.")
        return self._parse_transfer_receipt(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported Atlas receipt variant: {variant!r}.")
            return variant
        lines = lines_from_ocr(ocr)
        return self._detect_variant(ocr.text, lines)

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencia" not in norm or "enviada" not in norm:
            raise ParseError("Could not infer Atlas receipt variant from OCR.")
        has_anchor = (
            find_line_index(lines, "nro. de operacion") is not None
            or find_line_index(lines, "nro de operacion") is not None
            or find_line_index(lines, "remitente") is not None
            or find_line_index(lines, "cuenta origen") is not None
        )
        if not has_anchor:
            raise ParseError("Could not infer Atlas receipt variant from OCR.")
        return AtlasVariant.TRANSFER_RECEIPT

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
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(lines),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        operation = self._value_after_label(lines, "nro. de operacion") or self._value_after_label(
            lines, "nro de operacion"
        )
        if operation:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.OPERATION,
                    value=_sanitize_operation_id(operation),
                    label="Nro. de Operación",
                )
            )
        external = self._value_after_label(lines, "ref. externa") or self._value_after_label(
            lines, "ref externa"
        )
        if external:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.REFERENCE,
                    value=external.strip(),
                    label="Ref. Externa",
                )
            )
        return identifiers

    def _parse_sender(self, lines: list[str]) -> Party | None:
        sender_name = self._value_after_label(lines, "remitente")
        sender_account, sender_account_type = self._parse_cuenta_origen(lines)
        if not sender_name and not sender_account:
            return None
        return Party(
            name=sender_name,
            account=sender_account,
            account_type=sender_account_type,
        )

    def _parse_recipient(self, lines: list[str]) -> Party:
        return Party(
            name=self._party_name_after_label(lines, "beneficiario"),
            account=self._value_after_label(lines, "cuenta destino"),
            bank=self._value_after_label(lines, "entidad destino"),
        )

    def _parse_cuenta_origen(self, lines: list[str]) -> tuple[str | None, AccountType]:
        raw = self._value_after_label(lines, "cuenta origen")
        if raw is None:
            return None, AccountType.UNKNOWN
        if "|" in raw:
            type_part, account_part = raw.split("|", 1)
            account = account_part.strip()
            account_type = account_type_from_text(type_part.strip())
            return account or None, account_type
        return raw.strip() or None, AccountType.UNKNOWN

    def _parse_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        for line in lines:
            norm = normalize_label(line)
            if "monto" not in norm or "debito" not in norm:
                continue
            amount = _amount_in_text(line)
            if amount is not None:
                return amount
            same = value_on_same_line(line, "monto")
            if same:
                parsed = parse_decimal_amount(same) or _amount_in_text(same)
                if parsed is not None:
                    return parsed
        return extract_gs_amount(lines, full_text)

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        norm = normalize_label(full_text)
        if amount is None:
            return None
        if "guarani" in norm or re.search(r"\bgs\b", norm) or "gs." in norm:
            return "PYG"
        return None

    def _parse_occurred_at(self, lines: list[str], full_text: str) -> datetime | None:
        idx = find_line_index(lines, "fecha y hora de operacion")
        if idx is not None:
            chunk = lines[idx]
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                next_norm = normalize_label(next_line)
                if next_norm not in ("hs", "hs.") and re.search(
                    r"\d{2}/\d{2}/\d{4}", next_line
                ):
                    chunk = f"{chunk} {next_line}"
            parsed = parse_occurred_at(chunk)
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _value_after_label(
        self,
        lines: list[str],
        label: str,
        *,
        max_lookahead: int = 2,
    ) -> str | None:
        idx = find_line_index(lines, label)
        if idx is None:
            return None
        same_line = value_on_same_line(lines[idx], label)
        if same_line:
            return same_line.strip() or None
        for offset in range(1, max_lookahead + 1):
            pos = idx + offset
            if pos >= len(lines):
                break
            candidate = lines[pos].strip()
            if not candidate:
                continue
            if self._is_field_label(normalize_label(candidate)):
                break
            return candidate
        return None

    def _party_name_after_label(self, lines: list[str], label: str) -> str | None:
        idx = find_line_index(lines, label)
        if idx is None:
            return None
        same_line = value_on_same_line(lines[idx], label)
        if same_line:
            extra = collect_name_block(lines, idx + 1, max_lines=1)
            if extra:
                return f"{same_line} {extra}".strip()
            return same_line.strip() or None
        for offset in range(1, 3):
            pos = idx + offset
            if pos >= len(lines):
                break
            candidate = lines[pos].strip()
            if not candidate or self._is_field_label(normalize_label(candidate)):
                break
            if offset == 1:
                extra = collect_name_block(lines, pos + 1, max_lines=1)
                if extra:
                    return f"{candidate} {extra}".strip()
                return candidate
        return None

    def _is_field_label(self, normalized_line: str) -> bool:
        return any(normalized_line.startswith(prefix) for prefix in _FIELD_LABEL_PREFIXES)
