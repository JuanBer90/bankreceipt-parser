"""BNF (Banco Nacional de Fomento) transfer receipt parser."""

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
    find_exact_line,
    find_line_index,
    lines_from_ocr,
    normalize_label,
    value_on_same_line,
)
from bankreceipt_parser.parsers.common.party_names import natural_name_from_single_comma
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.bnf.variants import BnfVariant

_FIELD_LABEL_PREFIXES = (
    "destinatario",
    "cuenta",
    "entidad",
    "monto",
    "moneda",
    "tipo",
    "fecha",
    "nro",
    "concepto",
    "enviado",
    "banco",
    "detalle",
    "sip",
)


def _line_matching(lines: list[str], pattern: str) -> str | None:
    idx = find_line_index(lines, pattern)
    return lines[idx] if idx is not None else None


def _null_if_placeholder_concept(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped == ".":
        return None
    return stripped


class BnfReceiptParser:
    """Parse BNF transfer receipts from OCR text and layout."""

    issuer = Issuer.BNF
    supported_variants = frozenset(variant.value for variant in BnfVariant)

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
        if selected == BnfVariant.TRANSFER_SENT_CARD:
            return self._parse_transfer_sent_card(ocr, lines, country_code=country_code)
        return self._parse_operation_success_receipt(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        lines = lines_from_ocr(ocr)
        selected = self._detect_variant(ocr.text, lines) if variant is None else variant
        if selected not in self.supported_variants:
            raise ParseError(f"Unsupported BNF receipt variant: {selected!r}.")
        return selected

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "operacion exitosa" in norm:
            return BnfVariant.OPERATION_SUCCESS_RECEIPT
        if (
            find_line_index(lines, "entidad destino") is not None
            and find_line_index(lines, "tipo de cuenta") is not None
        ):
            return BnfVariant.TRANSFER_SENT_CARD
        if find_line_index(lines, "destinatario") is not None:
            return BnfVariant.TRANSFER_SENT_CARD
        raise ParseError("Could not infer BNF receipt variant from OCR.")

    def _parse_transfer_sent_card(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = extract_gs_amount(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(ocr.text, lines),
            status=TransferStatus.COMPLETED,
            raw_status=None,
            amount=amount,
            currency=self._parse_currency(lines, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text, "fecha y hora"),
            sender=self._parse_transfer_sent_sender(lines),
            recipient=self._parse_transfer_sent_recipient(lines),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_operation_success_receipt(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = extract_gs_amount(lines, ocr.text)
        status, raw_status = self._parse_operation_success_status(lines, ocr.text)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(ocr.text, lines),
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency=self._parse_currency(lines, amount),
            occurred_at=self._parse_occurred_at(lines, ocr.text, "fecha de operacion"),
            sender=self._parse_operation_success_sender(lines),
            recipient=self._parse_operation_success_recipient(lines),
            concept=self._parse_concept(lines),
            payment_network=payment_network_from_text(ocr.text),
            country_code=country_code,
        )

    def _parse_transfer_sent_sender(self, lines: list[str]) -> Party | None:
        sender_account = self._value_after_label(lines, "Cuenta origen")
        if not sender_account:
            return None
        account_type_text = self._value_after_label(lines, "Tipo de cuenta")
        account_type = (
            account_type_from_text(account_type_text) if account_type_text else AccountType.UNKNOWN
        )
        return Party(account=sender_account, account_type=account_type)

    def _parse_transfer_sent_recipient(self, lines: list[str]) -> Party:
        return Party(
            name=self._value_after_label(lines, "Destinatario", exact=True),
            account=self._value_after_label(lines, "Cuenta destino"),
            bank=self._value_after_label(lines, "Entidad destino"),
        )

    def _parse_operation_success_sender(self, lines: list[str]) -> Party | None:
        sender_name_raw = value_on_same_line(
            _line_matching(lines, "enviado por") or "",
            "enviado por",
        )
        if sender_name_raw is None:
            idx = find_line_index(lines, "enviado por")
            if idx is not None and idx + 1 < len(lines):
                candidate = lines[idx + 1].strip()
                if candidate and not self._is_field_label(normalize_label(candidate)):
                    sender_name_raw = candidate
        sender_name = (
            natural_name_from_single_comma(sender_name_raw) if sender_name_raw else None
        )
        return Party(name=sender_name) if sender_name else None

    def _parse_operation_success_recipient(self, lines: list[str]) -> Party:
        recipient_name, recipient_account = self._parse_operation_recipient(lines)
        recipient_bank = value_on_same_line(
            _line_matching(lines, "banco/cooperativa") or "",
            "banco/cooperativa",
        )
        if recipient_bank is None:
            recipient_bank = self._value_after_label(lines, "Banco/Cooperativa")
        return Party(
            name=recipient_name,
            account=recipient_account,
            bank=recipient_bank,
        )

    def _parse_identifiers(
        self,
        full_text: str,
        lines: list[str],
    ) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        patterns = (
            (r"Nro\.?\s*de\s*comprobante:?\s*(\d{4,})", "Nro. de comprobante"),
            (r"Nro\.?\s*Comprobante:?\s*(\d{4,})", "Nro. Comprobante"),
        )
        for pattern, label in patterns:
            match = re.search(pattern, full_text, flags=re.I)
            if match:
                identifiers.append(
                    TransactionIdentifier(
                        kind=TransactionIdentifierKind.TICKET,
                        value=match.group(1),
                        label=label,
                    )
                )
                return identifiers
        for line in lines:
            norm = normalize_label(line)
            if norm.startswith("nro. de comprobante") or norm.startswith("nro. comprobante"):
                digits = re.search(r"(\d{4,})", line)
                if digits:
                    identifiers.append(
                        TransactionIdentifier(
                            kind=TransactionIdentifierKind.TICKET,
                            value=digits.group(1),
                            label=(
                                line.split(":")[0].strip()
                                if ":" in line
                                else "Nro. de comprobante"
                            ),
                        )
                    )
                    return identifiers
        idx = find_line_index(lines, "nro. de comprobante")
        if idx is None:
            idx = find_line_index(lines, "nro. comprobante")
        if idx is not None and idx + 1 < len(lines):
            digits = re.search(r"(\d{4,})", lines[idx + 1])
            if digits:
                identifiers.append(
                    TransactionIdentifier(
                        kind=TransactionIdentifierKind.TICKET,
                        value=digits.group(1),
                        label="Nro. de Comprobante",
                    )
                )
        return identifiers

    def _parse_operation_recipient(self, lines: list[str]) -> tuple[str | None, str | None]:
        idx = find_line_index(lines, "cuenta destino")
        if idx is None:
            return None, None
        line = lines[idx]
        inline = value_on_same_line(line, "cuenta destino")
        name: str | None = None
        account: str | None = None
        if inline:
            if re.fullmatch(r"\d{6,12}", inline.replace(" ", "")):
                account = inline.strip()
            else:
                name = inline.strip()
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if re.fullmatch(r"\d{6,12}", next_line.replace(" ", "")):
                account = next_line
            elif (
                name is None
                and next_line
                and not self._is_field_label(normalize_label(next_line))
            ):
                name = next_line
        return name, account

    def _parse_operation_success_status(
        self,
        lines: list[str],
        full_text: str,
    ) -> tuple[TransferStatus, str | None]:
        norm_full = normalize_label(full_text)
        if "operacion exitosa" not in norm_full:
            return TransferStatus.UNKNOWN, None
        raw = self._extract_observed_operacion_exitosa_title(lines)
        return TransferStatus.COMPLETED, raw

    def _extract_observed_operacion_exitosa_title(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            norm = normalize_label(line)
            if "operacion exitosa" in norm:
                return line.strip()
            if norm in {"¡operacion", "operacion"} or norm.endswith("operacion"):
                parts = [line.strip()]
                if index + 1 < len(lines):
                    next_norm = normalize_label(lines[index + 1])
                    if "exitosa" in next_norm:
                        parts.append(lines[index + 1].strip())
                        return " ".join(parts)
        return None

    def _parse_concept(self, lines: list[str]) -> str | None:
        idx = find_line_index(lines, "concepto")
        if idx is None:
            return None
        value = value_on_same_line(lines[idx], "concepto")
        if value is None and idx + 1 < len(lines):
            value = lines[idx + 1].strip()
        return _null_if_placeholder_concept(value)

    def _parse_currency(self, lines: list[str], amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        for index, line in enumerate(lines):
            if "moneda" not in normalize_label(line):
                continue
            for nearby in lines[index : index + 3]:
                if "guarani" in normalize_label(nearby):
                    return "PYG"
        for line in lines:
            norm = normalize_label(line)
            if "monto" in norm and re.search(r"\bgs\b", norm.replace(".", "")):
                return "PYG"
            if re.search(r"\bgs\b", norm.replace(".", "")) and parse_decimal_amount(line) == amount:
                return "PYG"
        return None

    def _parse_occurred_at(
        self,
        lines: list[str],
        full_text: str,
        label_pattern: str,
    ) -> datetime | None:
        idx = find_line_index(lines, label_pattern)
        if idx is None:
            return parse_occurred_at(full_text)
        for offset in range(0, 2):
            pos = idx + offset
            if pos < len(lines):
                parsed = parse_occurred_at(lines[pos])
                if parsed is not None:
                    return parsed
        return parse_occurred_at(lines[idx]) or parse_occurred_at(full_text)

    def _value_after_label(
        self,
        lines: list[str],
        label: str,
        *,
        exact: bool = False,
        max_lookahead: int = 2,
    ) -> str | None:
        idx = find_exact_line(lines, label) if exact else find_line_index(lines, label)
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

    def _is_field_label(self, normalized_line: str) -> bool:
        return any(normalized_line.startswith(prefix) for prefix in _FIELD_LABEL_PREFIXES)
