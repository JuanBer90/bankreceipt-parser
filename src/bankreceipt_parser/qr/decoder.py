"""QR decoding (stubs)."""

from __future__ import annotations

from bankreceipt_parser.exceptions import QRDecodeError


def decode_qr_from_image(image: bytes) -> str | None:
    """Decode QR payload from image bytes. Implementation pending."""
    raise QRDecodeError("QR decoding is not implemented.")
