"""GNB (Grupo Nación / GNB) transfer receipt parser."""

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
    find_exact_line,
    find_line_index,
    lines_from_ocr,
    normalize_label,
    value_on_same_line,
)
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.gnb.variants import GnbVariant

_LABEL_PREFIXES = (
    "titular",
    "beneficiario",
    "entidad",
    "cuenta",
    "monto",
    "importe",
    "fecha",
    "hora",
    "concepto",
    "alias",
    "documento",
    "tipo",
    "moneda",
    "nro",
    "numero",
    "referencia",
    "nombre",
    "banco",
)


def _inline_value_on_label_line(line: str, label: str) -> str | None:
    norm_line = normalize_label(line)
    norm_label = normalize_label(label)
    if norm_label not in norm_line:
        return None
    if ":" in line:
        return None
    start = norm_line.find(norm_label)
    if start < 0:
        return None
    words = line.split()
    label_words = label.split()
    if len(words) <= len(label_words):
        return None
    tail = " ".join(words[len(label_words) :]).strip()
    return tail or None


def _amount_in_text(text: str) -> Decimal | None:
    match = re.search(r"[\d.]+", text.replace("Gs.", "").replace("Gs", ""))
    if not match:
        return None
    return parse_decimal_amount(match.group(0))


def _normalize_document_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    match = re.search(r"(\d[\d.]*)", cleaned.replace("CI", "").replace("-", " "))
    if not match:
        return cleaned or None
    digits = re.sub(r"\D", "", match.group(1))
    return digits or None


class GnbReceiptParser:
    """Parse GNB transfer receipts from OCR text and layout."""

    issuer = Issuer.GNB
    supported_variants = frozenset(variant.value for variant in GnbVariant)

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
        if selected == GnbVariant.SPI_MOVEMENT_DETAIL:
            return self._parse_spi_movement_detail(ocr, lines, country_code=country_code)
        return self._parse_transfer_success(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported GNB receipt variant: {variant!r}.")
            return variant
        lines = lines_from_ocr(ocr)
        return self._detect_variant(ocr.text, lines)

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "bgnbpyp" in norm and all(
            token in norm for token in ("transferencia", "enviada", "spi")
        ):
            return GnbVariant.SPI_MOVEMENT_DETAIL
        if find_line_index(lines, "banco-destinatario") is not None:
            return GnbVariant.SPI_MOVEMENT_DETAIL
        if "transferencia exitosa" in norm:
            return GnbVariant.TRANSFER_SUCCESS
        raise ParseError("Could not infer GNB receipt variant from OCR.")

    def _parse_transfer_success(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._parse_amount(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_transfer_success_identifiers(ocr.text, lines),
            status=TransferStatus.COMPLETED,
            raw_status="Transferencia Exitosa",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at_transfer_success(lines, ocr.text),
            sender=self._parse_transfer_success_sender(lines),
            recipient=self._parse_transfer_success_recipient(lines),
            concept=self._value_after_labeled_line(lines, "concepto"),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_spi_movement_detail(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = extract_gs_amount(lines, ocr.text)
        sender_account = self._value_after_exact_line(lines, "cuenta")
        account_type_line = self._value_after_exact_line(lines, "tipo")
        sender: Party | None = None
        if sender_account or account_type_line:
            sender = Party(
                account=sender_account,
                account_type=(
                    account_type_from_text(account_type_line)
                    if account_type_line
                    else AccountType.UNKNOWN
                ),
            )
        document_raw = self._value_after_labeled_line(lines, "documento-destinatario")
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_spi_identifiers(ocr.text, lines),
            status=TransferStatus.UNKNOWN,
            raw_status=None,
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at_spi(lines, ocr.text),
            sender=sender,
            recipient=Party(
                name=self._value_after_labeled_line(lines, "nombre-destinatario"),
                account=self._value_after_labeled_line(lines, "cuenta-destinatario"),
                bank=self._value_after_labeled_line(lines, "banco-destinatario"),
                document_identifier=_normalize_document_value(document_raw),
                alias=None,
            ),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_transfer_success_sender(self, lines: list[str]) -> Party | None:
        sender_name = self._party_name_after_label(lines, "titular")
        sender_account = self._value_after_labeled_line(lines, "cuenta debitada")
        if not sender_name and not sender_account:
            return None
        return Party(name=sender_name, account=sender_account)

    def _parse_transfer_success_recipient(self, lines: list[str]) -> Party:
        document_id = self._value_after_labeled_line(lines, "documento beneficiario")
        alias = self._value_after_labeled_line(lines, "alias")
        return Party(
            name=self._party_name_after_label(lines, "beneficiario"),
            account=self._value_after_labeled_line(lines, "cuenta acreditada"),
            bank=self._value_after_labeled_line(lines, "entidad"),
            document_identifier=_normalize_document_value(document_id),
            alias=alias.strip() if alias else None,
        )

    def _parse_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        return (
            self._amount_after_label(lines, "importe")
            or extract_gs_amount(lines, full_text)
            or self._amount_after_label(lines, "monto")
        )

    def _parse_currency(self, full_text: str, amount: Decimal | None) -> str | None:
        norm = normalize_label(full_text)
        if amount is None:
            return None
        if "guarani" in norm or re.search(r"\bgs\b", norm) or "gs." in norm:
            return "PYG"
        return None

    def _parse_occurred_at_transfer_success(
        self,
        lines: list[str],
        full_text: str,
    ) -> datetime | None:
        idx = find_line_index(lines, "fecha y hora")
        if idx is None:
            return parse_occurred_at(full_text)
        chunk = lines[idx]
        if idx + 1 < len(lines) and re.search(r"\d{2}/\d{2}/\d{4}", lines[idx + 1]):
            chunk = f"{chunk} {lines[idx + 1]}"
        return parse_occurred_at(chunk) or parse_occurred_at(full_text)

    def _parse_occurred_at_spi(self, lines: list[str], full_text: str) -> datetime | None:
        fecha = self._value_after_label(lines, "fecha", max_lookahead=1)
        hora = self._value_after_label(lines, "hora", max_lookahead=1)
        if fecha and hora:
            parsed = parse_occurred_at(f"{fecha} {hora}")
            if parsed is not None:
                return parsed
        if fecha:
            parsed = parse_occurred_at(fecha)
            if parsed is not None:
                return parsed
        return parse_occurred_at(full_text)

    def _parse_transfer_success_identifiers(
        self,
        full_text: str,
        lines: list[str],
    ) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        operation = (
            self._value_after_labeled_line(lines, "nro. de operacion")
            or self._value_after_labeled_line(lines, "nro de operacion")
        )
        if operation:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.OPERATION,
                    value=operation.strip(),
                    label="Nro. de Operación",
                )
            )
        return identifiers

    def _parse_spi_identifiers(
        self,
        full_text: str,
        lines: list[str],
    ) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        comprobante = (
            self._value_after_label(lines, "numero de comprobante")
            or self._value_after_label(lines, "número de comprobante")
        )
        if comprobante:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.TICKET,
                    value=comprobante.strip(),
                    label="Número de comprobante",
                )
            )
        referencia = self._value_after_label(lines, "referencia")
        if referencia and "bgnbpyp" in normalize_label(referencia):
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.REFERENCE,
                    value=referencia.strip(),
                    label="Referencia",
                )
            )
        ref_banco = self._value_after_label(lines, "referencia-banco")
        if ref_banco:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.REFERENCE,
                    value=ref_banco.strip(),
                    label="Referencia-Banco",
                )
            )
        return identifiers

    def _find_labeled_line_index(self, lines: list[str], label: str) -> int | None:
        target = normalize_label(label)
        for index, line in enumerate(lines):
            norm = normalize_label(line)
            if target == "entidad":
                if norm.startswith("identidad"):
                    continue
                if norm.startswith("entidad ") or norm == "entidad":
                    return index
                continue
            if target == "alias":
                if norm.startswith("tipo de alias"):
                    continue
                if norm.startswith("alias ") or norm == "alias":
                    return index
                continue
            if norm.startswith(f"{target} ") or norm == target:
                return index
        return None

    def _value_after_labeled_line(
        self,
        lines: list[str],
        label: str,
        *,
        max_lookahead: int = 2,
    ) -> str | None:
        idx = self._find_labeled_line_index(lines, label)
        if idx is None:
            return None
        same_line = value_on_same_line(lines[idx], label)
        if same_line:
            return same_line.strip() or None
        inline = _inline_value_on_label_line(lines[idx], label)
        if inline:
            return inline
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
        idx = self._find_labeled_line_index(lines, label)
        if idx is None:
            return None
        first = _inline_value_on_label_line(lines[idx], label)
        if first is None:
            return self._value_after_labeled_line(lines, label)
        extra = collect_name_block(lines, idx + 1, max_lines=1)
        if extra:
            return f"{first} {extra}".strip()
        return first

    def _value_after_exact_line(self, lines: list[str], label: str) -> str | None:
        idx = find_exact_line(lines, label)
        if idx is None:
            return None
        if idx + 1 >= len(lines):
            return None
        candidate = lines[idx + 1].strip()
        if not candidate or self._is_field_label(normalize_label(candidate)):
            return None
        return candidate

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
        inline = _inline_value_on_label_line(lines[idx], label)
        if inline:
            return inline
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

    def _amount_after_label(self, lines: list[str], label: str) -> Decimal | None:
        idx = find_line_index(lines, label)
        if idx is not None:
            inline = _amount_in_text(lines[idx])
            if inline is not None:
                return inline
        raw = self._value_after_label(lines, label)
        if raw is None:
            return None
        return parse_decimal_amount(raw) or _amount_in_text(raw)

    def _is_field_label(self, normalized_line: str) -> bool:
        return any(normalized_line.startswith(prefix) for prefix in _LABEL_PREFIXES)
