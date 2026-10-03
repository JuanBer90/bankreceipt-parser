"""Payment network helper tests."""

from __future__ import annotations

from bankreceipt_parser.parsers.common.payment_network import payment_network_from_text


def test_payment_network_from_text_detects_sip() -> None:
    assert payment_network_from_text("Detalle: transferencia - SIP") == "SIP"


def test_payment_network_from_text_detects_spi() -> None:
    assert payment_network_from_text("Tipo Movimiento Transferencia enviada SPI") == "SPI"


def test_payment_network_from_text_absent() -> None:
    assert payment_network_from_text("Transferencia local") is None
