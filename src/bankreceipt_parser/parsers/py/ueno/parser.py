"""UENO (Paraguay) transfer receipt parser."""

from __future__ import annotations

import re
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
)
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.ueno.variants import UenoVariant

_ENVIASTE_DINERO_A_PREFIX = re.compile(r"Enviaste\s+dinero\s+a\s*", re.I)


def _compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _amount_with_nearby_currency(ocr: OCRResult) -> tuple[Decimal | None, bool]:
    """Find a number paired with a nearby OCR currency token in receipt content."""
    candidates: list[tuple[float, Decimal, bool]] = []
    for element in ocr.elements:
        amount = parse_decimal_amount(element.text)
        if amount is None or element.bbox.y > 0.45:
            continue
        for currency in ocr.elements:
            token = normalize_label(currency.text).replace(".", "")
            if token not in {"gs", "cs"}:
                continue
            if abs(currency.bbox.y - element.bbox.y) > 0.045:
                continue
            if abs(currency.bbox.x - element.bbox.x) > 0.32:
                continue
            candidates.append((element.bbox.y, amount, True))
            break
    if not candidates:
        return None, False
    _y, amount, pyg = min(candidates, key=lambda candidate: candidate[0])
    return amount, pyg


def _has_explicit_guarani_currency(lines: list[str]) -> bool:
    for index, line in enumerate(lines):
        if "moneda" not in normalize_label(line):
            continue
        for nearby in lines[index : index + 3]:
            if "guarani" in normalize_label(nearby):
                return True
    return False


def _has_currency_adjacent_to_amount(lines: list[str], amount: Decimal) -> bool:
    for index, line in enumerate(lines):
        if parse_decimal_amount(line) != amount:
            continue
        for nearby in lines[max(0, index - 1) : index + 2]:
            token = normalize_label(nearby).replace(".", "")
            if token in {"gs", "cs"}:
                return True
    return False


def _recipient_from_enviaste(full_text: str) -> str | None:
    for line in full_text.split("\n"):
        stripped = line.strip()
        prefix = _ENVIASTE_DINERO_A_PREFIX.match(stripped)
        if prefix:
            name = " ".join(stripped[prefix.end() :].split())
            if name:
                return name
    compact = _compact_whitespace(full_text)
    match = re.search(
        r"Enviaste\s+dinero\s+a\s+(.+?)(?=\s+(?:O\s+)?Enviada\b|\s+DETALLE\b|$)",
        compact,
        flags=re.I,
    )
    if match:
        name = " ".join(match.group(1).split())
        if name:
            return name
    for line in full_text.split("\n"):
        legacy = re.search(
            r"Enviaste\s+dinero\s+(.+?)\s+a\s*$",
            line.strip(),
            flags=re.I,
        )
        if legacy:
            name = " ".join(legacy.group(1).split())
            if name:
                return name
    legacy_compact = re.search(
        r"Enviaste\s+dinero\s+(.+?)\s+a(?:\s+Enviada\b|\s+DETALLE\b|$)",
        compact,
        flags=re.I,
    )
    if legacy_compact:
        name = " ".join(legacy_compact.group(1).split())
        if name:
            return name
    return None


def _recipient_from_transferiste(full_text: str) -> str | None:
    compact = _compact_whitespace(full_text)
    match = re.search(
        r"Transferiste\s+Gs\.?\s*[\d.]+\s+a\s+(.+?)(?:\s+Detalle\b|$)",
        compact,
        flags=re.I,
    )
    if match:
        return " ".join(match.group(1).split())
    match = re.search(r"Transferiste\s+Gs\.?\s*[\d.]+\s+(.+)", compact, flags=re.I)
    if match:
        tail = match.group(1).strip()
        if normalize_label(tail).startswith("a "):
            tail = tail[2:]
        tail = re.split(r"\bDetalle\b", tail, maxsplit=1)[0]
        cleaned = " ".join(tail.split())
        if cleaned and normalize_label(cleaned) != "a":
            return cleaned
    for line in full_text.split("\n"):
        if "transferiste" in normalize_label(line) and "gs" in normalize_label(line):
            match = re.search(r"Gs\.?\s*[\d.]+\s+(.+)", line, flags=re.I)
            if match:
                name = match.group(1).strip()
                if normalize_label(name) == "a":
                    continue
                return name
    return None


class UenoReceiptParser:
    """Parse UENO transfer receipts from OCR text and layout."""

    issuer = Issuer.UENO
    supported_variants = frozenset(variant.value for variant in UenoVariant)

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
        full = ocr.text
        selected_variant = self.resolve_variant(ocr, variant=variant)
        amount, currency = self._parse_amount_and_currency(ocr, lines, selected_variant)
        sender, recipient = self._parse_parties(lines, full, selected_variant)
        status, raw_status = self._parse_status(full, lines, variant=selected_variant)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(full, lines),
            status=status,
            raw_status=raw_status,
            amount=amount,
            currency=currency,
            occurred_at=parse_occurred_at(full),
            sender=sender,
            recipient=recipient,
            concept=self._parse_concept(lines),
            payment_network=payment_network_from_text(full),
            country_code=country_code,
        )

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        """Use a supplied detection variant, or infer one for direct parser callers."""
        lines = lines_from_ocr(ocr)
        selected_variant = self._detect_variant(ocr.text, lines) if variant is None else variant
        if selected_variant not in self.supported_variants:
            raise ParseError(f"Unsupported UENO receipt variant: {selected_variant!r}.")
        return selected_variant

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferiste" in norm:
            return UenoVariant.TRANSFER_SUMMARY
        if "detalle de movimiento" in norm or "detalle de la transferencia" in norm:
            return UenoVariant.MOVEMENT_DETAIL
        if "comprobante de pago" in norm or "débito" in norm or "debito" in norm:
            return UenoVariant.PAYMENT_RECEIPT
        if "comprobante de transferencia" in norm or (
            "comprobante" in norm and "transferencia" in norm
        ):
            return UenoVariant.TRANSFER_RECEIPT
        if find_line_index(lines, "para") is not None and find_line_index(lines, "de") is not None:
            return UenoVariant.TRANSFER_RECEIPT
        return UenoVariant.PAYMENT_RECEIPT

    def _parse_parties(
        self,
        lines: list[str],
        full_text: str,
        variant: str,
    ) -> tuple[Party | None, Party | None]:
        if variant == UenoVariant.TRANSFER_RECEIPT:
            return self._parse_de_para_sections(lines)
        if variant == UenoVariant.PAYMENT_RECEIPT:
            return self._parse_payment_comprobante_parties(lines)
        if variant == UenoVariant.MOVEMENT_DETAIL:
            return self._parse_movement_detail_parties(lines, full_text)
        if variant == UenoVariant.TRANSFER_SUMMARY:
            return None, self._parse_transferiste_recipient(lines, full_text)
        return None, None

    def _parse_status(
        self,
        full_text: str,
        lines: list[str],
        *,
        variant: str,
    ) -> tuple[TransferStatus, str | None]:
        payment_receipt = variant == UenoVariant.PAYMENT_RECEIPT

        for line in lines:
            norm = normalize_label(line)
            if "transferencia exitosa" in norm:
                return TransferStatus.COMPLETED, line.strip()
            if "transferencia enviada" in norm:
                return TransferStatus.COMPLETED, self._extract_explicit_raw_status(
                    line,
                    payment_receipt=payment_receipt,
                )
            if norm == "enviada" or norm.endswith(" enviada"):
                return TransferStatus.COMPLETED, self._extract_explicit_raw_status(
                    line,
                    payment_receipt=payment_receipt,
                )
        if "exitosa" in normalize_label(full_text):
            return TransferStatus.COMPLETED, "Transferencia exitosa"
        if "enviada" in normalize_label(full_text):
            if payment_receipt:
                return TransferStatus.COMPLETED, None
            return TransferStatus.COMPLETED, "Transferencia Enviada"
        return TransferStatus.UNKNOWN, None

    def _extract_explicit_raw_status(self, line: str, *, payment_receipt: bool) -> str | None:
        """Map a status line to display raw_status (badge vs transfer summary)."""
        norm = normalize_label(line)
        if "transferencia exitosa" in norm:
            return line.strip()
        if "transferencia enviada" in norm:
            return None if payment_receipt else line.strip()
        if re.search(r"\benviada\b", norm) and "transferencia" not in norm:
            return None if payment_receipt else "Enviada"
        return None

    def _parse_amount_and_currency(
        self,
        ocr: OCRResult,
        lines: list[str],
        variant: str,
    ) -> tuple[Decimal | None, str | None]:
        labeled_amount = extract_gs_amount(lines, ocr.text, variant=variant)
        layout_amount, layout_has_pyg = _amount_with_nearby_currency(ocr)
        amount = labeled_amount if labeled_amount is not None else layout_amount
        if amount is None:
            return None, None
        if (
            _has_explicit_guarani_currency(lines)
            or _has_currency_adjacent_to_amount(lines, amount)
            or (layout_amount == amount and layout_has_pyg)
        ):
            return amount, "PYG"
        return amount, None

    def _parse_identifiers(self, full_text: str, lines: list[str]) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        match = re.search(
            r"Nro\.?\s*de\s*comprobante:?\s*(\d{6,})",
            full_text,
            flags=re.I,
        )
        if match:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.TICKET,
                    value=match.group(1),
                    label="Nro. de comprobante",
                )
            )
        for line in lines:
            norm = normalize_label(line)
            if norm.startswith("nro. de comprobante"):
                digits = re.search(r"(\d{6,})", line)
                if digits and not any(i.value == digits.group(1) for i in identifiers):
                    identifiers.append(
                        TransactionIdentifier(
                            kind=TransactionIdentifierKind.TICKET,
                            value=digits.group(1),
                            label="Nro. de comprobante",
                        )
                    )
        return identifiers

    def _parse_concept(self, lines: list[str]) -> str | None:
        idx = find_line_index(lines, "concepto")
        if idx is None:
            return None
        parts: list[str] = []
        for offset in range(1, 4):
            if idx + offset >= len(lines):
                break
            line = lines[idx + offset]
            norm = normalize_label(line)
            if norm.startswith(("cuenta", "entidad", "moneda", "nro")):
                break
            parts.append(line.strip())
        return " ".join(parts).strip() or None

    def _parse_de_para_sections(self, lines: list[str]) -> tuple[Party | None, Party | None]:
        de_idx = find_exact_line(lines, "de")
        para_idx = find_exact_line(lines, "para")
        if de_idx is None or para_idx is None:
            return None, None

        sender_name = self._join_person_lines(lines, de_idx + 1)
        sender_account, sender_type = self._parse_caja_account(lines, de_idx + 1)
        sender_bank = self._bank_in_party_section(lines, de_idx + 1, para_idx)

        recipient_name = self._join_person_lines(lines, para_idx + 1)
        recipient_account, _ = self._parse_nro_account(lines, para_idx + 1)
        recipient_type = AccountType.UNKNOWN
        recipient_bank = self._bank_in_party_section(lines, para_idx + 1, len(lines))

        sender = Party(
            name=sender_name,
            bank=sender_bank,
            account=sender_account,
            account_type=sender_type,
        )
        recipient = Party(
            name=recipient_name,
            bank=recipient_bank,
            account=recipient_account,
            account_type=recipient_type,
        )
        return sender, recipient

    def _parse_payment_comprobante_parties(
        self,
        lines: list[str],
    ) -> tuple[Party | None, Party | None]:
        para_idx = find_line_index(lines, "para")
        recipient_name = None
        if para_idx is not None:
            name_idx = find_line_index(lines[para_idx:], "nombre")
            if name_idx is not None:
                recipient_name = self._join_person_lines(lines, para_idx + name_idx + 1)
            else:
                recipient_name = self._join_person_lines(lines, para_idx + 1)

        dest_account, dest_type = self._parse_account_after_label(lines, "cuenta destino")
        orig_account, orig_type = self._parse_account_after_label(lines, "cuenta origen")
        sender_bank = self._parse_bank_after_entidad(lines, origin=True)

        sender = Party(
            bank=sender_bank,
            account=orig_account,
            account_type=orig_type,
        )
        recipient = Party(
            name=recipient_name,
            account=dest_account,
            account_type=dest_type,
        )
        return sender, recipient

    def _parse_movement_detail_parties(
        self,
        lines: list[str],
        full_text: str,
    ) -> tuple[Party | None, Party | None]:
        dest_account, dest_type = self._parse_account_after_label(lines, "cuenta destino")
        orig_account, orig_type = self._parse_account_after_label(lines, "cuenta origen")
        sender_bank = self._parse_bank_after_entidad(lines, origin=True)

        recipient_name = _recipient_from_enviaste(full_text)
        sender = Party(
            bank=sender_bank,
            account=orig_account,
            account_type=orig_type,
        )
        recipient = Party(
            name=recipient_name,
            account=dest_account,
            account_type=dest_type,
        )
        return sender, recipient

    def _parse_transferiste_recipient(self, lines: list[str], full_text: str) -> Party | None:
        name = _recipient_from_transferiste(full_text)
        dest_account, dest_type = self._parse_account_after_label(lines, "cuenta destino")
        recipient_bank = self._parse_bank_after_entidad(lines, origin=False)
        if not any([name, dest_account, recipient_bank]):
            return None
        return Party(
            name=name,
            account=dest_account,
            account_type=dest_type,
            bank=recipient_bank,
        )

    def _parse_account_after_label(
        self,
        lines: list[str],
        label: str,
    ) -> tuple[str | None, AccountType]:
        target = normalize_label(label)
        for idx, line in enumerate(lines):
            norm = normalize_label(line)
            reversed_label = " ".join(reversed(target.split()))
            if target not in norm and reversed_label not in norm:
                continue
            for offset in range(0, 3):
                pos = idx + offset
                if pos >= len(lines):
                    break
                candidate = lines[pos]
                digits = re.search(r"\b(\d{5,12})\b", candidate)
                if digits:
                    return digits.group(1), account_type_from_text(candidate)
        return None, AccountType.UNKNOWN

    def _parse_bank_after_entidad(self, lines: list[str], *, origin: bool) -> str | None:
        label = "entidad origen" if origin else "entidad"
        idx = find_line_index(lines, label)
        if idx is None:
            return None
        value_index = idx + 1
        if value_index >= len(lines):
            return None
        value = lines[value_index].strip()
        if not value or self._is_field_label(normalize_label(value)):
            return None
        return value

    def _join_person_lines(self, lines: list[str], start: int, *, max_parts: int = 4) -> str | None:
        parts: list[str] = []
        for offset in range(max_parts):
            idx = start + offset
            if idx >= len(lines):
                break
            line = lines[idx].strip()
            norm = normalize_label(line)
            if not line:
                continue
            if any(
                token in norm
                for token in (
                    "caja",
                    "nro",
                    "cuenta",
                    "entidad",
                    "moneda",
                    "comprobante",
                    "operación",
                    "operacion",
                    "c.",
                    "cs.",
                )
            ):
                break
            if norm in {"de", "para", "a"}:
                continue
            parts.append(line)
        return " ".join(parts).strip() or None

    def _parse_caja_account(self, lines: list[str], start: int) -> tuple[str | None, AccountType]:
        for idx in range(start, min(start + 5, len(lines))):
            norm = normalize_label(lines[idx])
            if "caja" in norm and "ahorro" in norm:
                digits = re.search(r"\b(\d{5,12})\b", lines[idx])
                if digits:
                    return digits.group(1), account_type_from_text(lines[idx])
            if "nro" in norm and "comprobante" not in norm:
                digits = re.search(r"\b(\d{5,12})\b", lines[idx])
                if digits:
                    return digits.group(1), AccountType.UNKNOWN
        return None, AccountType.UNKNOWN

    def _parse_nro_account(self, lines: list[str], start: int) -> tuple[str | None, AccountType]:
        for idx in range(start, min(start + 4, len(lines))):
            norm = normalize_label(lines[idx])
            if norm.startswith("nro") or norm == "nro.":
                digits = re.search(r"\b(\d{5,12})\b", lines[idx])
                if digits:
                    return digits.group(1), AccountType.UNKNOWN
            digits = re.search(r"^\s*Nro\.?\s*(\d{5,12})\s*$", lines[idx], flags=re.I)
            if digits:
                return digits.group(1), AccountType.UNKNOWN
        return None, AccountType.UNKNOWN

    def _bank_in_party_section(self, lines: list[str], start: int, end: int) -> str | None:
        """Read an explicitly displayed bank immediately after a party account line."""
        for index in range(start, end):
            account_line = normalize_label(lines[index])
            if not (
                re.search(r"\b\d{5,12}\b", lines[index])
                and ("caja" in account_line or "cuenta" in account_line or "nro" in account_line)
            ):
                continue
            candidate_index = index + 1
            if candidate_index >= end:
                return None
            candidate = lines[candidate_index].strip()
            normalized = normalize_label(candidate)
            if (
                not candidate
                or normalized in {"de", "para", "a"}
                or self._is_field_label(normalized)
            ):
                return None
            if re.fullmatch(r"[\d.\-\s]+", candidate):
                return None
            return candidate
        return None

    def _is_field_label(self, normalized_line: str) -> bool:
        return normalized_line.startswith(
            (
                "moneda",
                "operación",
                "operacion",
                "nro",
                "mostrar",
                "cuenta",
                "entidad",
                "concepto",
                "comprobante",
                "fecha",
            )
        )
