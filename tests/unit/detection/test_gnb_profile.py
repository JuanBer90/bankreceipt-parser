"""Synthetic GNB issuer detection tests."""

from __future__ import annotations

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.profiles.py.gnb import GNB_SPI_MOVEMENT, GNB_TRANSFER_SUCCESS
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.2, y=y, width=0.5, height=0.03),
        line_index=int(y * 100),
    )


def _ocr(lines: list[tuple[str, float]]) -> OCRResult:
    return OCRResult(
        text="\n".join(text for text, _ in lines),
        image_width=400,
        image_height=900,
        elements=[_el(text, y) for text, y in lines],
    )


def _transfer_success_lines() -> list[tuple[str, float]]:
    return [
        ("GNB", 0.05),
        ("Transferencia Exitosa", 0.15),
        ("Gs. 20.000", 0.20),
        ("Nro. de Operación 77550001", 0.30),
    ]


def _spi_movement_lines() -> list[tuple[str, float]]:
    return [
        ("Tipo Movimiento", 0.05),
        ("Transferencia enviada SPI", 0.10),
        ("Cuenta", 0.15),
        ("13244000001", 0.18),
        ("Referencia", 0.50),
        ("BGNBPYPX30099999990064013099", 0.54),
    ]


def _spi_only_lines() -> list[tuple[str, float]]:
    return [
        ("Transferencia enviada SPI", 0.10),
        ("Monto", 0.20),
        ("Gs. 50.000", 0.24),
    ]


def test_gnb_transfer_success_profile_matches() -> None:
    ocr = _ocr(_transfer_success_lines())
    result = GNB_TRANSFER_SUCCESS.evaluate(ocr, None)
    assert result.accepted
    assert result.variant == "transfer_success"


def test_gnb_spi_profile_requires_institutional_reference() -> None:
    ocr = _ocr(_spi_movement_lines())
    result = GNB_SPI_MOVEMENT.evaluate(ocr, None)
    assert result.accepted
    assert "gnb_institutional_reference" in result.matched_signals
    assert "spi_transfer_context" in result.matched_signals


def test_gnb_spi_profile_rejects_spi_without_bgnbpyp() -> None:
    ocr = _ocr(_spi_only_lines())
    result = GNB_SPI_MOVEMENT.evaluate(ocr, None)
    assert not result.accepted


def test_detect_spi_movement_establishes_gnb_without_wordmark() -> None:
    outcome = detect_issuer_from_ocr(_ocr(_spi_movement_lines()))
    assert outcome.issuer == "gnb"
    assert outcome.variant == "spi_movement_detail"


def test_detect_transfer_success() -> None:
    outcome = detect_issuer_from_ocr(_ocr(_transfer_success_lines()))
    assert outcome.issuer == "gnb"
    assert outcome.variant == "transfer_success"
