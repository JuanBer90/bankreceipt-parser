"""Itaú Paraguay transfer receipt parser."""

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
from bankreceipt_parser.ocr.structure import OCRResult, OCRTextElement
from bankreceipt_parser.parsers.common.amounts import extract_gs_amount, parse_decimal_amount
from bankreceipt_parser.parsers.common.datetime_py import parse_occurred_at
from bankreceipt_parser.parsers.common.lines import (
    find_exact_line,
    find_line_index,
    lines_from_ocr,
    normalize_label,
    value_on_same_line,
)
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.itau.variants import ItauVariant

_FIELD_LABEL_PREFIXES = (
    "monto",
    "para",
    "de",
    "banco",
    "cuenta",
    "c.",
    "alias",
    "numero",
    "n°",
    "fecha",
    "situacion",
    "comprobante",
    "operacion",
    "realizada",
    "detalle",
    "sip",
)

_TRANSFER_RECEIPT_SIGNALS = (
    "comprobante de transferencia",
    "monto debito",
    "situacion de la transaccion",
    "n° de comprobante",
    "numero de comprobante",
)


class ItauReceiptParser:
    """Parse Itaú transfer receipts from OCR text and layout."""

    issuer = Issuer.ITAU
    supported_variants = frozenset(variant.value for variant in ItauVariant)

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
        if selected == ItauVariant.TRANSACTION_REGISTERED:
            return self._parse_transaction_registered(ocr, lines, country_code=country_code)
        return self._parse_transfer_receipt(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        lines = lines_from_ocr(ocr)
        selected = self._detect_variant(ocr.text, lines) if variant is None else variant
        if selected not in self.supported_variants:
            raise ParseError(f"Unsupported Itaú receipt variant: {selected!r}.")
        return selected

    # Variant parsing

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        has_transfer = any(signal in norm for signal in _TRANSFER_RECEIPT_SIGNALS)
        has_registered = "transaccion registrada" in norm
        if has_transfer:
            return ItauVariant.TRANSFER_RECEIPT
        if has_registered:
            return ItauVariant.TRANSACTION_REGISTERED
        raise ParseError("Could not infer Itaú receipt variant from OCR.")

    def _parse_transaction_registered(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._extract_amount(lines, ocr.text)
        currency = self._parse_currency(lines, amount)
        payment_network = payment_network_from_text(ocr.text)
        status, raw_status = self._parse_transaction_registered_status(lines)
        recipient_name = self._recipient_name_after_para(lines, ocr)
        recipient_bank = self._bank_after_banco_de_la_cuenta_label(lines)
        document_id = self._value_after_ci_label(lines)
        recipient = Party(
            name=recipient_name,
            bank=recipient_bank,
            document_identifier=document_id,
        )
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=[],
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency=currency,
            occurred_at=None,
            sender=None,
            recipient=recipient,
            payment_network=payment_network,
            country_code=country_code,
        )


    def _parse_transfer_receipt(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount = self._extract_amount(lines, ocr.text)
        currency = self._parse_currency(lines, amount)
        payment_network = payment_network_from_text(ocr.text)
        identifiers = self._parse_identifiers(lines)
        status, raw_status = self._parse_transfer_receipt_status(lines)
        occurred_at = self._parse_occurred_at(lines)
        sender, recipient = self._parse_transfer_parties(ocr, lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=identifiers,
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency=currency,
            occurred_at=occurred_at,
            sender=sender,
            recipient=recipient,
            payment_network=payment_network,
            country_code=country_code,
        )

    # Status

    def _parse_transaction_registered_status(
        self,
        lines: list[str],
    ) -> tuple[TransferStatus, str | None]:
        for line in lines:
            norm = normalize_label(line)
            if "transaccion registrada" in norm and "correctamente" in norm:
                return TransferStatus.PENDING, line.strip()
        return TransferStatus.UNKNOWN, None


    def _parse_transfer_receipt_status(self, lines: list[str]) -> tuple[TransferStatus, str | None]:
        idx = find_line_index(lines, "situacion de la transaccion")
        if idx is None:
            return TransferStatus.UNKNOWN, None
        for offset in range(1, 4):
            pos = idx + offset
            if pos >= len(lines):
                break
            candidate = lines[pos].strip()
            if not candidate:
                continue
            norm = normalize_label(candidate)
            if _is_field_label(norm):
                break
            if _transfer_status_indicates_completed(norm):
                return TransferStatus.COMPLETED, candidate
            return TransferStatus.UNKNOWN, candidate
        return TransferStatus.UNKNOWN, None

    def _parse_occurred_at(self, lines: list[str]) -> datetime | None:
        for line in lines:
            if "realizada el" in normalize_label(line):
                parsed = parse_occurred_at(line)
                if parsed is not None:
                    return parsed
        idx = find_line_index(lines, "fecha y hora de recepcion")
        if idx is not None:
            for offset in range(1, 4):
                pos = idx + offset
                if pos >= len(lines):
                    break
                candidate = lines[pos].strip()
                if not candidate:
                    continue
                norm = normalize_label(candidate)
                if norm.startswith("fecha de movimiento"):
                    break
                parsed = parse_occurred_at(candidate)
                if parsed is not None:
                    return parsed
        return None

    # Parties

    def _parse_transfer_parties(
        self,
        ocr: OCRResult,
        lines: list[str],
    ) -> tuple[Party | None, Party | None]:
        sender = self._parse_sender_party(lines)
        recipient = self._parse_recipient_party(ocr, lines)
        return sender, recipient


    def _parse_sender_party(self, lines: list[str]) -> Party | None:
        debit_account = self._debit_account_from_lines(lines)
        name = self._name_after_de_label(lines)
        if name is None and debit_account is None:
            return self._parse_detailed_sender(lines)
        if debit_account is None:
            detailed = self._parse_detailed_sender(lines)
            if detailed is not None and detailed.account:
                debit_account = detailed.account
            if name is None and detailed is not None:
                name = detailed.name
        if name is None and debit_account is None:
            return None
        return Party(name=name, account=debit_account)


    def _parse_detailed_sender(self, lines: list[str]) -> Party | None:
        de_idx = self._find_de_party_index(lines)
        if de_idx is None:
            return None
        name = self._line_value_after_index(lines, de_idx)
        if name is None:
            return None
        cuenta_idx = _index_of_first_cuenta_guaranies(lines, start=de_idx + 1)
        account = None
        if cuenta_idx is not None:
            account = _account_on_or_after_line(lines, cuenta_idx)
        return Party(name=name, account=account)


    def _find_para_line_index(self, lines: list[str]) -> int | None:
        exact = find_exact_line(lines, "para")
        if exact is not None:
            return exact
        for index, line in enumerate(lines):
            tokens = normalize_label(line).split()
            if "para" in tokens:
                return index
        return None


    def _parse_recipient_party(self, ocr: OCRResult, lines: list[str]) -> Party | None:
        para_idx = self._find_para_line_index(lines)
        if para_idx is not None and self._should_use_layout_recipient(ocr, lines, para_idx):
            layout_party = self._recipient_from_layout_elements(ocr, lines)
            if layout_party is not None and layout_party.name:
                alias = self._value_after_alias_label(lines)
                if alias and layout_party.alias is None:
                    layout_party = layout_party.model_copy(update={"alias": alias})
                return layout_party
        if para_idx is not None:
            name = self._recipient_name_after_para(lines, ocr)
            if name is None:
                name = self._fallback_recipient_name(lines)
            alias = self._value_after_alias_label(lines)
            document_id = self._value_after_ci_label(lines)
            bank = self._bank_after_banco_de_la_cuenta_label(lines)
            account = self._recipient_account_from_lines(lines)
            return Party(
                name=name,
                bank=bank,
                account=account,
                alias=alias,
                document_identifier=document_id,
            )
        return self._parse_detailed_recipient(lines)


    def _parse_detailed_recipient(self, lines: list[str]) -> Party | None:
        de_idx = self._find_de_party_index(lines)
        if de_idx is None:
            return None
        first_cuenta_idx = _index_of_first_cuenta_guaranies(lines, start=de_idx + 1)
        if first_cuenta_idx is None:
            return None
        second_cuenta_idx = _index_of_first_cuenta_guaranies(lines, start=first_cuenta_idx + 1)
        if second_cuenta_idx is None:
            return None
        cursor = first_cuenta_idx + 1
        if cursor < len(lines) and re.search(r"n°\s*\d", lines[cursor], flags=re.I):
            cursor += 1
        block_lines: list[str] = []
        while cursor < second_cuenta_idx:
            line = lines[cursor].strip()
            if line:
                block_lines.append(line)
            cursor += 1
        name, bank = self._split_detailed_recipient_block(block_lines)
        if name is None:
            return None
        account = _account_on_or_after_line(lines, second_cuenta_idx)
        return Party(name=name, bank=bank, account=account)


    def _split_detailed_recipient_block(
        self,
        block_lines: list[str],
    ) -> tuple[str | None, str | None]:
        if not block_lines:
            return None, None
        if len(block_lines) == 1:
            return block_lines[0], None
        if (
            len(block_lines) == 2
            and _looks_like_name_line(block_lines[0])
            and _looks_like_name_line(block_lines[1])
            and not _line_looks_like_institution_label(block_lines[1])
        ):
            return " ".join(block_lines), None
        name = " ".join(block_lines[:-1]).strip()
        bank = block_lines[-1].strip() or None
        return name or None, bank


    def _recipient_account_from_lines(self, lines: list[str]) -> str | None:
        indices = [
            index
            for index, line in enumerate(lines)
            if "cuenta en guaranies" in normalize_label(line)
            or "cuenta en guaranies" in normalize_label(line.replace("í", "i"))
        ]
        if not indices:
            idx = find_line_index(lines, "cuenta en guaranies")
            if idx is None:
                return None
            indices = [idx]
        last_idx = indices[-1]
        return _account_on_or_after_line(lines, last_idx)


    def _recipient_name_after_para(self, lines: list[str], ocr: OCRResult) -> str | None:
        para_idx = self._find_para_line_index(lines)
        if para_idx is None:
            return None
        if ocr.elements and self._should_use_layout_recipient(ocr, lines, para_idx):
            party = self._recipient_from_layout_elements(ocr, lines)
            return party.name if party else None
        return self._name_lines_after_para(lines, para_idx)


    def _name_lines_after_para(self, lines: list[str], para_idx: int) -> str | None:
        parts: list[str] = []
        for offset in range(1, 5):
            pos = para_idx + offset
            if pos >= len(lines):
                break
            line = lines[pos].strip()
            norm = normalize_label(line)
            if not line:
                continue
            if norm.startswith("banco de la cuenta") or norm.startswith("banco de"):
                break
            if _is_field_label(norm) or _is_alias_or_ci_label(line):
                break
            if re.fullmatch(r"\d{4,}", line.replace(" ", "")):
                break
            if _looks_like_name_line(line):
                parts.append(line)
                continue
            if parts:
                break
        joined = " ".join(parts).strip()
        return joined or None


    def _should_use_layout_recipient(self, ocr: OCRResult, lines: list[str], para_idx: int) -> bool:
        _ = para_idx
        if find_line_index(lines, "comprobante de transferencia") is None:
            return False
        return bool(ocr.elements and _find_para_element(ocr.elements) is not None)


    def _recipient_from_layout_elements(self, ocr: OCRResult, lines: list[str]) -> Party | None:
        anchor = _find_para_element(ocr.elements)
        if anchor is None:
            return None
        y_min = anchor.bbox.y + anchor.bbox.height * 0.5
        y_max = _layout_recipient_y_max(anchor, ocr.elements)
        cutoff = _recipient_column_cutoff_x(anchor, ocr.elements)
        column_min_x = anchor.bbox.x - 0.03
        window = [
            element
            for element in ocr.elements
            if y_min <= element.bbox.y <= y_max
            and element.text.strip()
            and element.bbox.x >= column_min_x
            and element.bbox.x + element.bbox.width * 0.5 < cutoff
        ]
        on_para_band = [e for e in ocr.elements if abs(e.bbox.y - anchor.bbox.y) < 0.028]
        qr_on_para = False
        if len(on_para_band) >= 2:
            xs = sorted(e.bbox.x for e in on_para_band)
            qr_on_para = xs[-1] - xs[0] > 0.22
        filtered = (
            _filter_receipt_column_elements(window, anchor) if qr_on_para else window
        )
        name_parts: list[str] = []
        bank_parts: list[str] = []
        account: str | None = None
        for group in _cluster_elements_by_line(filtered):
            text = _join_elements(group).strip()
            norm = normalize_label(text)
            if norm == "para" or _is_qr_garbage(text) or _is_recipient_layout_noise(text):
                continue
            if "cuenta" in norm and ("guaranies" in norm or "guaraníes" in text.casefold()):
                account = _digits_from_group(group) or _account_from_text(text)
                continue
            if norm.startswith("n°") or re.fullmatch(r"n°\s*\d{6,12}", text, flags=re.I):
                digits = _account_from_text(text)
                if digits:
                    account = digits
                continue
            if "numero de comprobante" in norm or norm.startswith("n° de comprobante"):
                break
            if _line_looks_like_institution_label(text):
                bank_parts.append(text)
                continue
            layout_name = _layout_name_from_element_group(group, anchor)
            if layout_name:
                name_parts.append(layout_name)
            elif _looks_like_name_line(text) and not _is_qr_garbage(text):
                name_parts.append(text)
        name = " ".join(name_parts).strip() or None
        bank = " ".join(bank_parts).strip() or None
        if name is None and bank is None and account is None:
            return None
        return Party(name=name, bank=bank, account=account)

    # Identifiers

    def _parse_identifiers(self, lines: list[str]) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        ticket = self._ticket_from_lines(lines)
        if ticket:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.TICKET,
                    value=re.sub(r"\D", "", ticket) or ticket,
                    label="N° de comprobante",
                )
            )
        operation = self._operation_id_from_lines(lines)
        if operation:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.OPERATION,
                    value=operation.strip(),
                    label="N° de operación",
                )
            )
        return identifiers


    def _value_after_label(
        self,
        lines: list[str],
        label: str,
        *,
        max_lookahead: int = 3,
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
            if _is_field_label(normalize_label(candidate)):
                break
            return candidate
        return None


    def _ticket_from_lines(self, lines: list[str]) -> str | None:
        for label in ("n° de comprobante", "numero de comprobante"):
            idx = find_line_index(lines, label)
            if idx is None:
                continue
            inline = _digits_tail_on_label_line(lines[idx], label)
            if inline:
                return inline
            if idx + 1 < len(lines):
                norm = normalize_label(lines[idx + 1])
                if not _is_field_label(norm):
                    match = re.search(r"(\d{4,})", lines[idx + 1])
                    if match:
                        return match.group(1)
        return None


    def _operation_id_from_lines(self, lines: list[str]) -> str | None:
        inline_pattern = re.compile(
            r"n[°º]?\s*de\s*operaci[oó]n\s*:?\s*(\S+)",
            flags=re.I,
        )
        for line in lines:
            match = inline_pattern.search(line)
            if match and _is_plausible_operation_id(match.group(1)):
                return match.group(1).strip()
        for label in ("n° de operacion", "n° de operación"):
            idx = find_line_index(lines, label)
            if idx is None:
                continue
            for offset in range(0, 3):
                pos = idx + offset
                if pos >= len(lines):
                    break
                if offset == 0:
                    match = inline_pattern.search(lines[pos])
                    if match and _is_plausible_operation_id(match.group(1)):
                        return match.group(1).strip()
                    continue
                candidate = lines[pos].strip()
                if not candidate:
                    continue
                norm = normalize_label(candidate)
                if _is_field_label(norm) or _looks_like_fecha_label(norm):
                    break
                if _is_plausible_operation_id(candidate):
                    return candidate
        return None


    def _bank_after_banco_de_la_cuenta_label(self, lines: list[str]) -> str | None:
        idx = find_line_index(lines, "banco de la cuenta")
        if idx is None:
            return None
        match = re.search(r"banco de la cuenta\s*:?\s*(.+)$", lines[idx], flags=re.I)
        if match:
            value = match.group(1).strip()
            if value:
                return value
        for offset in range(1, 3):
            pos = idx + offset
            if pos >= len(lines):
                break
            candidate = lines[pos].strip()
            if not candidate:
                continue
            norm = normalize_label(candidate)
            if _is_field_label(norm) or _is_alias_or_ci_label(candidate):
                break
            if re.fullmatch(r"c\.?\s*l\.?", candidate, flags=re.I):
                break
            return candidate
        return None


    def _value_after_ci_label(self, lines: list[str]) -> str | None:
        for index, line in enumerate(lines):
            stripped = line.strip()
            if re.fullmatch(r"c\.?\s*l\.?", stripped, flags=re.I) and index + 1 < len(lines):
                return _validated_ci_value(lines[index + 1])
        idx = find_line_index(lines, "c.i")
        if idx is not None:
            match = re.search(r"c\.?\s*i\.?\s*:?\s*(\S+)", lines[idx], flags=re.I)
            if match:
                return _validated_ci_value(match.group(1))
            if idx + 1 < len(lines):
                return _validated_ci_value(lines[idx + 1])
        return None


    def _value_after_alias_label(self, lines: list[str]) -> str | None:
        idx = find_line_index(lines, "alias")
        if idx is not None:
            match = re.search(r"alias\s*:?\s*(\S+)", lines[idx], flags=re.I)
            if match:
                validated = _validated_alias_value(match.group(1))
                if validated:
                    return validated
            if idx + 1 < len(lines):
                return _validated_alias_value(lines[idx + 1])
        for index, line in enumerate(lines):
            norm = normalize_label(line.strip())
            if norm in {"alias", "ci"} and index + 1 < len(lines):
                return _validated_alias_value(lines[index + 1])
        return None


    def _fallback_recipient_name(self, lines: list[str]) -> str | None:
        sender_name = self._name_after_de_label(lines)
        for line in lines:
            if _looks_like_name_line(line) and len(line.split()) >= 2:
                stripped = line.strip()
                if sender_name and stripped == sender_name:
                    continue
                norm = normalize_label(line)
                if "banco" in norm or "comprobante" in norm:
                    continue
                if "debito" in norm or "guaranies" in norm:
                    continue
                return stripped
        return None

    # Amount / currency / datetime

    def _extract_amount(self, lines: list[str], full_text: str) -> Decimal | None:
        amount = extract_gs_amount(lines, full_text)
        if amount is not None:
            return amount
        for line in lines:
            if re.search(r"\bgs\.?\b", line, flags=re.I):
                match = re.search(r"([\d. ,]+)\s*gs\.?", line, flags=re.I)
                if match:
                    parsed = parse_decimal_amount(match.group(1))
                    if parsed is not None:
                        return parsed
                match = re.search(r"gs\.?\s*([\d. ,]+)", line, flags=re.I)
                if match:
                    parsed = parse_decimal_amount(match.group(1))
                    if parsed is not None:
                        return parsed
        return None


    def _name_after_de_label(self, lines: list[str]) -> str | None:
        idx = self._find_de_party_index(lines)
        if idx is None:
            return None
        return self._line_value_after_index(lines, idx)


    def _find_de_party_index(self, lines: list[str]) -> int | None:
        for index, line in enumerate(lines):
            norm = normalize_label(line)
            if norm == "de" or norm.endswith(" de") or norm == "a de":
                return index
            if norm.endswith(" de") and len(norm) <= 6:
                return index
        idx = find_line_index(lines, "de")
        if idx is not None:
            norm = normalize_label(lines[idx])
            if norm == "de" or "cuenta debito" in normalize_label(lines[idx]):
                return idx
        for index, line in enumerate(lines):
            if normalize_label(line) == "de":
                return index
        return None


    def _line_value_after_index(self, lines: list[str], index: int) -> str | None:
        line = lines[index].strip()
        norm = normalize_label(line)
        if norm == "de":
            if index + 1 < len(lines):
                candidate = lines[index + 1].strip()
                if candidate and not _is_field_label(normalize_label(candidate)):
                    return candidate
            return None
        if " de" in norm and norm != "de":
            parts = re.split(r"\bde\b", line, maxsplit=1, flags=re.I)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
        if index + 1 < len(lines):
            candidate = lines[index + 1].strip()
            if (
                candidate
                and not _is_field_label(normalize_label(candidate))
                and "cuenta" not in normalize_label(candidate)
            ):
                return candidate
        return None


    def _debit_account_from_lines(self, lines: list[str]) -> str | None:
        idx = find_line_index(lines, "cuenta debito")
        if idx is None:
            return None
        on_label_line = _account_on_or_after_line(lines, idx)
        if on_label_line:
            return on_label_line
        for offset in range(1, 4):
            pos = idx + offset
            if pos >= len(lines):
                break
            norm = normalize_label(lines[pos])
            if _is_field_label(norm):
                continue
            found = _account_on_or_after_line(lines, pos)
            if found:
                return found
        return None


    def _account_after_label(self, lines: list[str], label: str) -> str | None:
        idx = find_line_index(lines, label)
        if idx is None:
            return None
        inline = value_on_same_line(lines[idx], label)
        if inline:
            digits = re.search(r"(\d{6,12})", inline.replace(" ", ""))
            if digits:
                return digits.group(1)
        for offset in range(0, 3):
            pos = idx + offset
            if pos < len(lines):
                found = _account_on_or_after_line(lines, pos)
                if found:
                    return found
        return None


    def _first_account_after_index(self, lines: list[str], start: int) -> str | None:
        idx = _index_of_first_cuenta_guaranies(lines, start=start)
        if idx is None:
            return None
        return _account_on_or_after_line(lines, idx)


    def _parse_currency(self, lines: list[str], amount: Decimal | None) -> str | None:
        if amount is None:
            return None
        for line in lines:
            norm = normalize_label(line)
            has_gs = re.search(r"\bgs\b", norm.replace(".", "")) or "guarani" in norm
            if has_gs and (parse_decimal_amount(line) == amount or "gs" in norm):
                return "PYG"
        for line in lines:
            if re.search(r"\bgs\b", normalize_label(line).replace(".", "")):
                return "PYG"
        return None


# Status helpers


def _transfer_status_indicates_completed(normalized_status_line: str) -> bool:
    if "procesada" in normalized_status_line:
        return True
    if "operacion exitosa" in normalized_status_line:
        return True
    return "enviada" in normalized_status_line and "transferencia" in normalized_status_line


# OCR / layout helpers


def _layout_name_from_element_group(
    group: list[OCRTextElement],
    anchor: OCRTextElement,
) -> str | None:
    ordered = sorted(group, key=lambda e: e.bbox.x)
    start_index: int | None = None
    for index, element in enumerate(ordered):
        token = element.text.strip()
        if len(token) < 4:
            continue
        if element.bbox.x + 0.001 < anchor.bbox.x:
            continue
        if not re.search(r"[a-záéíóúñ]", token, flags=re.I):
            continue
        if _is_recipient_layout_noise(token):
            continue
        start_index = index
        break
    if start_index is None:
        return None
    tokens: list[str] = []
    for element in ordered[start_index:]:
        token = element.text.strip()
        if not token or _is_recipient_layout_noise(token):
            continue
        if tokens and len(token) <= 2 and token.islower():
            continue
        tokens.append(token)
    joined = " ".join(tokens).strip()
    return joined or None


def _recipient_column_cutoff_x(anchor: OCRTextElement, elements: list[OCRTextElement]) -> float:
    on_line = [e for e in elements if abs(e.bbox.y - anchor.bbox.y) < 0.028]
    if len(on_line) >= 2:
        xs = sorted(e.bbox.x for e in on_line)
        if xs[-1] - xs[0] > 0.22:
            return anchor.bbox.x + anchor.bbox.width + 0.32
    return min(0.95, anchor.bbox.x + 0.62)


def _layout_recipient_y_max(anchor: OCRTextElement, elements: list[OCRTextElement]) -> float:
    limit = anchor.bbox.y + 0.45
    for element in elements:
        if element.bbox.y <= anchor.bbox.y + 0.015:
            continue
        norm = normalize_label(element.text)
        if norm in {"numero", "realizada", "ci", "alias"}:
            limit = min(limit, element.bbox.y - 0.008)
        if "comprobante" in norm and element.bbox.y > anchor.bbox.y + 0.05:
            limit = min(limit, element.bbox.y - 0.008)
    return limit


def _is_recipient_layout_noise(text: str) -> bool:
    norm = normalize_label(text)
    if re.fullmatch(r"\d{4,}", text.replace(" ", "")):
        return True
    if norm in {"ci", "alias", "fa"}:
        return True
    if "realizada" in norm or "comprobante" in norm:
        return True
    return bool(re.search(r"\b\d{1,2}\s+oct\b", norm) or re.search(r"\b20\d{2}\b", norm))


def _find_para_element(elements: list[OCRTextElement]) -> OCRTextElement | None:
    for element in elements:
        if normalize_label(element.text) == "para":
            return element
    return None


def _has_qr_noise_on_para_line(ocr: OCRResult, para_line_idx: int) -> bool:
    _ = para_line_idx
    if not ocr.elements:
        return False
    anchor = _find_para_element(ocr.elements)
    if anchor is None:
        return False
    on_line = [e for e in ocr.elements if abs(e.bbox.y - anchor.bbox.y) < 0.028]
    if len(on_line) < 2:
        return False
    xs = sorted(e.bbox.x for e in on_line)
    return xs[-1] - xs[0] > 0.22


def _filter_receipt_column_elements(
    elements: list[OCRTextElement],
    anchor: OCRTextElement,
) -> list[OCRTextElement]:
    groups = _cluster_elements_by_line(elements)
    kept: list[OCRTextElement] = []
    for group in groups:
        kept.extend(_left_cluster_or_all(group, anchor))
    return kept


def _left_cluster_or_all(
    group: list[OCRTextElement],
    anchor: OCRTextElement,
) -> list[OCRTextElement]:
    ordered = sorted(group, key=lambda e: e.bbox.x)
    if len(ordered) <= 1:
        return ordered
    gaps: list[tuple[float, int]] = []
    for index in range(len(ordered) - 1):
        left = ordered[index]
        right = ordered[index + 1]
        gap = right.bbox.x - (left.bbox.x + left.bbox.width)
        gaps.append((gap, index))
    max_gap, split_at = max(gaps, key=lambda item: item[0])
    median_w = sorted(e.bbox.width for e in ordered)[len(ordered) // 2]
    if max_gap > max(median_w * 2.5, 0.06):
        left_part = ordered[: split_at + 1]
        if any(normalize_label(e.text) == "para" for e in left_part):
            return left_part
        if all(e.bbox.x < anchor.bbox.x + anchor.bbox.width + 0.35 for e in left_part):
            return left_part
        return ordered[: split_at + 1]
    if all(e.bbox.x < anchor.bbox.x + anchor.bbox.width + 0.4 for e in ordered):
        return ordered
    return [e for e in ordered if e.bbox.x < anchor.bbox.x + anchor.bbox.width + 0.38]


def _cluster_elements_by_line(elements: list[OCRTextElement]) -> list[list[OCRTextElement]]:
    if not elements:
        return []
    sorted_elements = sorted(elements, key=lambda e: (e.bbox.y, e.bbox.x))
    clusters: list[list[OCRTextElement]] = []
    current: list[OCRTextElement] = [sorted_elements[0]]
    for element in sorted_elements[1:]:
        if abs(element.bbox.y - current[-1].bbox.y) <= 0.028:
            current.append(element)
        else:
            clusters.append(current)
            current = [element]
    clusters.append(current)
    return clusters


def _join_elements(group: list[OCRTextElement]) -> str:
    return " ".join(e.text for e in sorted(group, key=lambda e: e.bbox.x))


def _digits_from_group(group: list[OCRTextElement]) -> str | None:
    for element in group:
        match = re.search(r"\d{6,12}", element.text.replace(" ", ""))
        if match:
            return match.group(0)
    return None


def _account_from_text(text: str) -> str | None:
    match = re.search(r"n°\s*(\d{6,12})", text, flags=re.I)
    if match:
        return match.group(1)
    digits = re.search(r"\b(\d{6,12})\b", text.replace(" ", ""))
    return digits.group(1) if digits else None


# Validation / text helpers


def _is_field_label(normalized_line: str) -> bool:
    return any(normalized_line.startswith(prefix) for prefix in _FIELD_LABEL_PREFIXES)


def _is_qr_garbage(text: str) -> bool:
    norm = normalize_label(text)
    if "http" in norm or "@" in text:
        return True
    return bool(len(text) > 40 and not re.search(r"[a-z]{3,}", norm))


def _digits_on_next_line(lines: list[str], label_pattern: str) -> str | None:
    idx = find_line_index(lines, label_pattern)
    if idx is None or idx + 1 >= len(lines):
        return None
    match = re.search(r"(\d{4,})", lines[idx + 1])
    return match.group(1) if match else None


def _is_plausible_operation_id(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 8:
        return False
    if _looks_like_fecha_label(normalize_label(stripped)):
        return False
    if parse_occurred_at(stripped) is not None:
        return False
    return bool(re.search(r"[A-Za-z0-9]", stripped))


def _digits_tail_on_label_line(line: str, label: str) -> str | None:
    if normalize_label(label) not in normalize_label(line):
        return None
    match = re.search(r"(\d{4,})", line)
    return match.group(1) if match else None


def _validated_ci_value(raw: str) -> str | None:
    candidate = raw.strip()
    if not candidate:
        return None
    norm = normalize_label(candidate)
    if _is_field_label(norm) or _looks_like_fecha_label(norm):
        return None
    if parse_occurred_at(candidate) is not None:
        return None
    return candidate


def _validated_alias_value(raw: str) -> str | None:
    candidate = raw.strip()
    if not candidate:
        return None
    norm = normalize_label(candidate)
    if _is_field_label(norm) or _looks_like_fecha_label(norm):
        return None
    if not re.search(r"\d", candidate):
        return None
    return candidate


def _looks_like_fecha_label(normalized_line: str) -> bool:
    return normalized_line.startswith("fecha") or "fecha y hora" in normalized_line


def _line_looks_like_institution_label(text: str) -> bool:
    norm = normalize_label(text)
    if not norm or "banco de la cuenta" in norm:
        return False
    institution_markers = ("banco", "cooperativa", "ltda", "financier", "sociedad")
    return any(marker in norm for marker in institution_markers)


def _is_alias_or_ci_label(line: str) -> bool:
    norm = normalize_label(line.strip())
    return norm in {"alias", "ci"} or bool(re.fullmatch(r"c\.?\s*l\.?", line.strip(), flags=re.I))


def _account_on_or_after_line(lines: list[str], index: int) -> str | None:
    for pos in range(index, min(index + 2, len(lines))):
        match = re.search(r"n°\s*(\d{6,12})", lines[pos], flags=re.I)
        if match:
            return match.group(1)
        match = re.search(r"\b(\d{6,12})\b", lines[pos].replace(" ", ""))
        if match and "comprobante" not in normalize_label(lines[pos]):
            return match.group(1)
    return None


def _index_of_first_cuenta_guaranies(lines: list[str], *, start: int) -> int | None:
    for index in range(start, len(lines)):
        norm = normalize_label(lines[index])
        if "cuenta en guaranies" in norm or "cuenta en guaraníes" in lines[index].casefold():
            return index
    return None


def _looks_like_name_line(text: str) -> bool:
    norm = normalize_label(text)
    if not norm or _is_field_label(norm):
        return False
    if _is_recipient_layout_noise(text):
        return False
    if "realizada" in norm or "comprobante" in norm:
        return False
    if re.fullmatch(r"\d{6,12}", text.replace(" ", "")):
        return False
    if "banco" in norm and "s.a" in norm:
        return False
    return bool(re.search(r"[a-záéíóúñ]", text, flags=re.I))

