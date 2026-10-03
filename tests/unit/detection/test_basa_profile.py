"""BASA issuer profile tests (synthetic images/text only)."""

from __future__ import annotations

from PIL import Image, ImageDraw

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.basa import BASA_TRANSFER_SUCCESS
from bankreceipt_parser.detection.signals.order import VerticalOrderSignal
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _el(text: str, y: float, x: float = 0.25) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=x, y=y, width=0.3, height=0.04),
        line_index=1,
    )


def _basa_like_image() -> Image.Image:
    image = Image.new("RGB", (400, 900), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 400, 180), fill=(0, 80, 180))
    draw.ellipse((150, 120, 250, 220), fill=(90, 185, 158))
    return image


def _basa_like_ocr(*, include_solar: bool = False) -> OCRResult:
    lines = [
        _el("Transferencia", 0.20, 0.25),
        _el("exitosa", 0.20, 0.58),
        _el("Monto", 0.45),
        _el("Fecha", 0.52),
        _el("Compartir", 0.85, 0.28),
        _el("comprobante", 0.85, 0.50),
    ]
    text = (
        "Transferencia exitosa\nDestino inventado\nMonto\nFecha\nCompartir comprobante"
    )
    if include_solar:
        text = "Solar Banco destino\n" + text
        lines.insert(2, _el("Solar", 0.32))
    return OCRResult(text=text, image_width=400, image_height=900, elements=lines)


def test_vertical_order_monto_before_fecha() -> None:
    ocr = _basa_like_ocr()
    signal = VerticalOrderSignal(
        signal_id="order",
        upper_phrases=("monto",),
        lower_phrases=("fecha",),
        weight=0.8,
    )
    matched, score = signal.evaluate(ocr)
    assert matched is True
    assert score == 0.8


def test_basa_profile_accepts_synthetic_layout() -> None:
    ocr = _basa_like_ocr()
    image = _basa_like_image()
    result = BASA_TRANSFER_SUCCESS.evaluate(ocr, image)
    assert result.accepted is True


def test_solar_banco_text_does_not_establish_basa_without_layout() -> None:
    ocr = _basa_like_ocr(include_solar=True)
    plain = Image.new("RGB", (400, 900), color=(245, 245, 245))
    outcome = detect_issuer_from_ocr(ocr, image=plain)
    assert outcome.issuer != "basa"


def test_basa_detection_on_synthetic_success_screen() -> None:
    ocr = _basa_like_ocr(include_solar=True)
    outcome = detect_issuer_from_ocr(ocr, image=_basa_like_image())
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == "basa"
    assert outcome.variant == "transfer_success"


def test_basa_party_cards_profile_accepts_stacked_layout_text() -> None:
    from bankreceipt_parser.detection.profiles.py.basa import BASA_PARTY_CARDS

    ocr = OCRResult(
        text=(
            "Transferencia exitosa\nGs. 20.000\n"
            "Remitente\nBanco Basa - AH-100\n"
            "Comprobante: 99\nRealizado el: 01/01/2026 a las 10:00"
        ),
        image_width=400,
        image_height=900,
        elements=[
            _el("Transferencia exitosa", 0.20),
            _el("Banco Basa", 0.40),
            _el("Comprobante", 0.60),
        ],
    )
    result = BASA_PARTY_CARDS.evaluate(ocr, None)
    assert result.accepted
