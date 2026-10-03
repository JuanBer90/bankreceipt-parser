"""Minimal example using the public parse API."""

from __future__ import annotations

import sys

from bankreceipt_parser import __version__, parse


def main() -> None:
    if len(sys.argv) < 2:
        print(f"bankreceipt-parser {__version__}")
        print("Usage: python examples/basic.py <receipt-image.png>")
        sys.exit(1)

    result = parse(sys.argv[1])
    if result.receipt is None:
        for warning in result.warnings:
            print(warning)
        sys.exit(2)

    receipt = result.receipt
    print(f"issuer={receipt.issuer} ({receipt.issuer_display_name})")
    print(f"amount={receipt.amount} {receipt.currency}")
    if receipt.sender:
        print(f"sender={receipt.sender.name}")
    if receipt.recipient:
        print(f"recipient={receipt.recipient.name}")


if __name__ == "__main__":
    main()
