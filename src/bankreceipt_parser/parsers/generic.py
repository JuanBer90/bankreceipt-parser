"""Fallback parser when issuer is unknown."""

from __future__ import annotations

from bankreceipt_parser.exceptions import ParseError
from bankreceipt_parser.models.receipt import BankTransferReceipt


class GenericReceiptParser:
    """Minimal stub; does not extract fields yet."""

    issuer = "generic"

    def parse_text(
        self,
        text: str,
        *,
        qr_data: str | None = None,
        country_code: str | None = None,
    ) -> BankTransferReceipt:
        _ = (text, qr_data)
        raise ParseError("Generic parsing is not implemented.")
