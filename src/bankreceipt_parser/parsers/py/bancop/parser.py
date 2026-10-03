"""BANCOP mobile transfer screen parser."""

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
from bankreceipt_parser.parsers.common.lines import find_line_index, lines_from_ocr, normalize_label
from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text
from bankreceipt_parser.parsers.py.bancop.variants import BancopVariant

_ACCOUNT_IN_LINE = re.compile(
    r"(?:N[°ºo]\s*)?(\d{6,14})(?:\s*\|\s*Gs\.?)?",
    re.I,
)
_REF_LINE = re.compile(r"Ref:\s*(\d{6,12})", re.I)
# Destino name/bank share one row; institution text sits right of the name column.
_DESTINO_RIGHT_COLUMN_X = 0.55


def _section_index(lines: list[str], label: str) -> int | None:
    target = normalize_label(label)
    for index, line in enumerate(lines):
        norm = normalize_label(line)
        if target in norm and len(norm) <= len(target) + 4:
            return index
    return find_line_index(lines, label)


def _account_from_line(line: str) -> str | None:
    match = _ACCOUNT_IN_LINE.search(line)
    return match.group(1) if match else None


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) <= 2:
        return True
    norm = normalize_label(stripped)
    if norm in {"a", "y", "04", "o"}:
        return True
    return bool(re.fullmatch(r"\(\w\)", stripped))


def _gs_amount_in_line(line: str) -> Decimal | None:
    match = re.search(r"Gs\.?\s*([\d.]+)", line, flags=re.I)
    if match:
        return parse_decimal_amount(match.group(1))
    return None


def _concept_from_monto_line(line: str) -> str | None:
    without_amount = re.sub(r"Gs\.?\s*[\d.]+", "", line, flags=re.I).strip()
    return without_amount or None


def _is_destino_value_token(text: str) -> bool:
    stripped = text.strip()
    if not stripped or "|" in stripped:
        return False
    norm = normalize_label(stripped)
    if norm in {"de", "cuenta", "nro", "gs", "tipo", "alias", "nombre", "apellido"}:
        return False
    return not bool(re.fullmatch(r"\d+", stripped))


def _column_tokens(
    ocr: OCRResult,
    y_min: float,
    y_max: float,
    *,
    left_column: bool,
) -> str:
    parts: list[tuple[float, float, str]] = []
    for element in ocr.elements:
        if not (y_min <= element.bbox.y <= y_max):
            continue
        if not _is_destino_value_token(element.text):
            continue
        if left_column and element.bbox.x < _DESTINO_RIGHT_COLUMN_X:
            parts.append((element.bbox.y, element.bbox.x, element.text))
        if not left_column and element.bbox.x >= _DESTINO_RIGHT_COLUMN_X:
            parts.append((element.bbox.y, element.bbox.x, element.text))
    parts.sort()
    return " ".join(text for _y, _x, text in parts).strip()


def _label_element_y(ocr: OCRResult, label: str) -> float | None:
    target = normalize_label(label)
    for element in ocr.elements:
        if normalize_label(element.text) == target:
            return element.bbox.y
    for element in ocr.elements:
        norm = normalize_label(element.text)
        if target in norm and len(norm) <= len(target) + 5:
            return element.bbox.y
    return None


class BancopReceiptParser:
    """Parse BANCOP transfer confirmation screens."""

    issuer = Issuer.BANCOP
    supported_variants = frozenset(variant.value for variant in BancopVariant)

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
        if selected != BancopVariant.TRANSFER_SCREEN:
            raise ParseError(f"Unsupported BANCOP receipt variant: {selected!r}.")
        return self._parse_transfer_screen(ocr, lines, country_code=country_code)

    def resolve_variant(self, ocr: OCRResult, *, variant: str | None = None) -> str:
        if variant is not None:
            if variant not in self.supported_variants:
                raise ParseError(f"Unsupported BANCOP receipt variant: {variant!r}.")
            return variant
        return self._detect_variant(ocr.text, lines_from_ocr(ocr))

    def _detect_variant(self, full_text: str, lines: list[str]) -> str:
        norm = normalize_label(full_text)
        if "transferencias" not in norm:
            raise ParseError("Could not infer BANCOP receipt variant from OCR.")
        if "operacion realizada" not in norm:
            raise ParseError("Could not infer BANCOP receipt variant from OCR.")
        if _section_index(lines, "origen") is None or _section_index(lines, "destino") is None:
            raise ParseError("Could not infer BANCOP receipt variant from OCR.")
        return BancopVariant.TRANSFER_SCREEN

    def _parse_transfer_screen(
        self,
        ocr: OCRResult,
        lines: list[str],
        *,
        country_code: str | None,
    ) -> BankTransferReceipt:
        amount, concept = self._parse_amount_and_concept(lines)
        return BankTransferReceipt(
            issuer=self.issuer,
            transaction_identifiers=self._parse_identifiers(ocr.text, lines),
            status=TransferStatus.COMPLETED,
            raw_status="Operación realizada",
            amount=amount,
            currency=self._parse_currency(ocr.text, amount),
            occurred_at=self._parse_occurred_at(ocr.text),
            sender=self._parse_sender(lines),
            recipient=self._parse_recipient(ocr, lines),
            concept=concept,
            payment_network=payment_network_from_text(ocr.text),
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

    def _parse_amount_and_concept(self, lines: list[str]) -> tuple[Decimal | None, str | None]:
        header = find_line_index(lines, "monto")
        if header is not None and header + 1 < len(lines):
            value_line = lines[header + 1]
            amount = _gs_amount_in_line(value_line) or parse_decimal_amount(value_line)
            concept = _concept_from_monto_line(value_line)
            if amount is not None:
                return amount, concept
        amount = extract_gs_amount(lines, "\n".join(lines))
        return amount, None

    def _parse_identifiers(
        self,
        full_text: str,
        lines: list[str],
    ) -> list[TransactionIdentifier]:
        identifiers: list[TransactionIdentifier] = []
        ref = _REF_LINE.search(full_text)
        if ref:
            identifiers.append(
                TransactionIdentifier(
                    kind=TransactionIdentifierKind.TICKET,
                    value=ref.group(1),
                    label="Ref",
                )
            )
        comprobante_idx = find_line_index(lines, "comprobante")
        if comprobante_idx is not None and comprobante_idx + 1 < len(lines):
            match = re.search(r"(\d{6,12})", lines[comprobante_idx + 1])
            if match:
                ticket = match.group(1)
                if not identifiers or identifiers[0].value != ticket:
                    identifiers.append(
                        TransactionIdentifier(
                            kind=TransactionIdentifierKind.TICKET,
                            value=ticket,
                            label="Nro. de comprobante",
                        )
                    )
        return identifiers

    def _parse_sender(self, lines: list[str]) -> Party | None:
        origen = _section_index(lines, "origen")
        destino = _section_index(lines, "destino")
        if origen is None or destino is None or destino <= origen:
            return None
        name: str | None = None
        account: str | None = None
        account_type = AccountType.UNKNOWN
        for line in lines[origen + 1 : destino]:
            if _is_noise_line(line):
                continue
            norm = normalize_label(line)
            if "corriente" in norm or "ahorro" in norm or "n°" in norm or "n " in norm:
                account = account or _account_from_line(line)
                if account_type == AccountType.UNKNOWN:
                    account_type = account_type_from_text(line)
                continue
            if account is None and not re.search(r"\d{6,}", line):
                name = line.strip()
        if not name and not account:
            return None
        return Party(name=name, account=account, account_type=account_type)

    def _parse_recipient(self, ocr: OCRResult, lines: list[str]) -> Party | None:
        destino = _section_index(lines, "destino")
        if destino is None:
            return None
        account: str | None = None
        for line in lines[destino + 1 :]:
            norm = normalize_label(line)
            if "monto" in norm:
                break
            parsed = _account_from_line(line)
            if parsed:
                account = parsed
                break
        y_destino = _label_element_y(ocr, "destino")
        y_cuenta_label = _label_element_y(ocr, "nro.")
        name: str | None = None
        bank: str | None = None
        y_field_headers = _label_element_y(ocr, "nombre")
        if y_destino is not None and y_cuenta_label is not None and ocr.elements:
            y_min = (y_field_headers or y_destino) + 0.022
            y_max = y_cuenta_label - 0.02
            if y_max > y_min:
                name = _column_tokens(ocr, y_min, y_max, left_column=True) or None
                bank = _column_tokens(ocr, y_min, y_max, left_column=False) or None
        alias = self._parse_recipient_alias(lines, destino)
        if not name and not bank and not account:
            return None
        return Party(name=name, account=account, bank=bank, alias=alias)

    def _parse_recipient_alias(self, lines: list[str], destino: int) -> str | None:
        for line in lines[destino:]:
            match = re.match(r"^CI\s+(\d+)\s*$", line.strip(), flags=re.I)
            if match:
                return match.group(1)
        return None
