"""Transaction identifier types."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TransactionIdentifierKind(StrEnum):
    """Known identifier labels found on receipts."""

    REFERENCE = "reference"
    AUTHORIZATION = "authorization"
    TICKET = "ticket"
    TRACE = "trace"
    OPERATION = "operation"
    OTHER = "other"


class TransactionIdentifier(BaseModel):
    """A single transaction reference from the receipt."""

    kind: TransactionIdentifierKind = TransactionIdentifierKind.OTHER
    value: str
    label: str | None = Field(default=None, description="Raw label text from the receipt.")
