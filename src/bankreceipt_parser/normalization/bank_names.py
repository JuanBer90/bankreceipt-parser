"""Canonical bank names for extracted party fields."""

from __future__ import annotations

import re

from bankreceipt_parser.models.issuer import metadata_for
from bankreceipt_parser.normalization.registry import BANK_NAME_RULES, BankNameRule
from bankreceipt_parser.parsers.common.lines import normalize_label


def _tokenize_bank_name(text: str) -> frozenset[str]:
    normalized = normalize_label(text)
    normalized = re.sub(r"\bs\.?\s*a\.?\b", " sa ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return frozenset(re.findall(r"[a-z0-9]+", normalized))


def _canonical_for_rule(rule: BankNameRule) -> str:
    if rule.canonical_name is not None:
        return rule.canonical_name
    if rule.issuer is None:
        raise ValueError("BankNameRule matched without canonical_name or issuer.")
    return metadata_for(rule.issuer).display_name


def _rule_matches(tokens: frozenset[str], rule: BankNameRule) -> bool:
    if rule.match_mode == "exact":
        return tokens == rule.required_tokens
    return rule.required_tokens <= tokens


def normalize_bank_name(extracted: str) -> str:
    """
    Map a parser-extracted bank label to a canonical name when recognized.

    Returns ``extracted`` unchanged when no rule matches with sufficient certainty.
    """
    tokens = _tokenize_bank_name(extracted)
    for rule in BANK_NAME_RULES:
        if _rule_matches(tokens, rule):
            return _canonical_for_rule(rule)
    return extracted
