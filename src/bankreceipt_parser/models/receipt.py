"""Normalized bank transfer receipt domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field

from bankreceipt_parser.models.enums import AccountType, TransferStatus
from bankreceipt_parser.models.identifier import TransactionIdentifier
from bankreceipt_parser.models.issuer import display_name_for_issuer_slug
from bankreceipt_parser.models.party import BankParty, Party


class BankTransferReceipt(BaseModel):
    """Structured, normalized view of a bank transfer receipt."""

    issuer: str = Field(description="Detected issuer key (e.g. bank slug or parser id).")
    transaction_identifiers: list[TransactionIdentifier] = Field(default_factory=list)
    status: TransferStatus = TransferStatus.UNKNOWN
    raw_status: str | None = Field(
        default=None,
        description="Status text as printed on the receipt.",
    )
    amount: Decimal | None = None
    currency: str | None = Field(default=None, description="ISO 4217 code when known.")
    occurred_at: datetime | None = Field(
        default=None,
        description=(
            "Local wall-clock time printed on the receipt; timezone is unavailable "
            "unless encoded by the source."
        ),
    )
    sender: Party | None = None
    recipient: Party | None = None
    bank: BankParty | None = None
    account: str | None = Field(
        default=None,
        description="Full account number when explicitly shown.",
    )
    masked_account: str | None = None
    account_type: AccountType = AccountType.UNKNOWN
    alias: str | None = Field(
        default=None,
        description="Payment alias (e.g. SPI alias) when present.",
    )
    concept: str | None = Field(default=None, description="Transfer description or concept.")
    payment_network: str | None = None
    qr_data: str | None = Field(default=None, description="Raw payload from QR when decoded.")
    country_code: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country for the parser jurisdiction.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def issuer_display_name(self) -> str | None:
        """Human-readable issuer name from :data:`ISSUER_METADATA` (not from OCR)."""
        return display_name_for_issuer_slug(self.issuer)
