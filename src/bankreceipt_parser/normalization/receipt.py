"""Apply bank-name normalization to parsed receipts."""

from __future__ import annotations

from bankreceipt_parser.models.party import BankParty, Party
from bankreceipt_parser.models.receipt import BankTransferReceipt
from bankreceipt_parser.normalization.bank_names import normalize_bank_name


def _normalize_party(party: Party | None) -> Party | None:
    if party is None or party.bank is None:
        return party
    canonical = normalize_bank_name(party.bank)
    if canonical == party.bank:
        return party
    return party.model_copy(update={"bank": canonical})


def _normalize_bank_party(bank: BankParty | None) -> BankParty | None:
    if bank is None or bank.name is None:
        return bank
    canonical = normalize_bank_name(bank.name)
    if canonical == bank.name:
        return bank
    return bank.model_copy(update={"name": canonical})


def normalize_receipt_bank_names(receipt: BankTransferReceipt) -> BankTransferReceipt:
    """Normalize extracted bank labels on sender, recipient, and top-level bank."""
    sender = _normalize_party(receipt.sender)
    recipient = _normalize_party(receipt.recipient)
    bank = _normalize_bank_party(receipt.bank)
    if sender is receipt.sender and recipient is receipt.recipient and bank is receipt.bank:
        return receipt
    return receipt.model_copy(
        update={
            "sender": sender,
            "recipient": recipient,
            "bank": bank,
        }
    )
