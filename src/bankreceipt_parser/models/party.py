"""Parties involved in a transfer (sender, recipient, bank)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from bankreceipt_parser.models.enums import AccountType


class Party(BaseModel):
    """A person or entity named on a receipt."""

    name: str | None = None
    document_identifier: str | None = Field(
        default=None,
        description="National ID, RUC, or similar document number when present.",
    )
    bank: str | None = Field(default=None, description="Institution for this party when shown.")
    account: str | None = Field(default=None, description="Account number when explicitly shown.")
    masked_account: str | None = None
    account_type: AccountType = AccountType.UNKNOWN
    alias: str | None = Field(default=None, description="Payment alias when present.")


class BankParty(BaseModel):
    """Bank institution reference."""

    name: str | None = None
    code: str | None = Field(default=None, description="Bank or SWIFT-like code when known.")
