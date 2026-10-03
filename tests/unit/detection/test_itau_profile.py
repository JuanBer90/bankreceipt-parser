"""ITAU issuer profile tests (synthetic images/text only)."""

from __future__ import annotations

from PIL import Image, ImageDraw

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profiles.py.itau import (
    ITAU_TRANSFER_RECEIPT,
    ITAU_VISUAL_ISSUER,
)
from bankreceipt_parser.detection.signals.layout import NormalizedRegion
from bankreceipt_parser.detection.signals.visual import BrandBlockSignal, BrandDensitySignal
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _element(text: str, y: float) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.5, height=0.04),
        line_index=1,
    )


def _itau_orange_header(*, wide: bool = False) -> Image.Image:
    image = Image.new("RGB", (400, 800), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    if wide:
        draw.rectangle((0, 0, 220, 90), fill=(255, 98, 0))
    else:
        draw.rectangle((0, 0, 120, 90), fill=(255, 98, 0))
    return image


def test_brand_density_accepts_synthetic_itau_orange_band() -> None:
    signal = BrandDensitySignal(
        signal_id="density",
        region=NormalizedRegion(x=0.0, y=0.0, width=0.55, height=0.28),
        target_rgb=(255, 98, 0),
        tolerance=40.0,
        min_coverage=0.33,
        min_median_red=254.0,
        max_median_blue=15.0,
        weight=1.0,
    )
    matched, score = signal.evaluate(_itau_orange_header(wide=True))
    assert matched is True
    assert score == 1.0


def test_brand_block_prefers_left_clustered_logo() -> None:
    signal = BrandBlockSignal(
        signal_id="block",
        region=NormalizedRegion(x=0.0, y=0.0, width=0.55, height=0.28),
        target_rgb=(255, 98, 0),
        tolerance=40.0,
        min_left_coverage=0.10,
        min_left_bias=0.55,
        max_median_blue=15.0,
        min_median_red=248.0,
        weight=1.0,
    )
    left_ok, _ = signal.evaluate(_itau_orange_header(wide=False))
    wide_ok, _ = signal.evaluate(_itau_orange_header(wide=True))
    assert left_ok is True
    assert wide_ok is False


def test_visual_issuer_profile_on_synthetic_header() -> None:
    ocr = OCRResult(
        text="Comprobante transferencia",
        image_width=400,
        image_height=800,
        elements=[],
    )
    image = _itau_orange_header(wide=True)
    result = ITAU_VISUAL_ISSUER.evaluate(ocr, image)
    assert result.accepted is True


def test_itau_transfer_variant_from_generic_comprobante_text() -> None:
    ocr = OCRResult(
        text="Comprobante de transferencia",
        image_width=100,
        image_height=200,
        elements=[_element("Comprobante de transferencia", 0.1)],
    )
    result = ITAU_TRANSFER_RECEIPT.evaluate(ocr, None)
    assert result.accepted is True


def test_movimiento_without_itau_visual_or_brand_stays_unknown() -> None:
    ocr = OCRResult(
        text="Detalle de movimiento",
        image_width=100,
        image_height=200,
        elements=[_element("Detalle de movimiento", 0.1)],
    )
    plain = Image.new("RGB", (400, 800), color=(245, 245, 245))
    outcome = detect_issuer_from_ocr(ocr, image=plain)
    assert outcome.status == DetectionStatus.UNKNOWN
    assert outcome.issuer != "itau"


def test_yellow_bank_header_does_not_match_itau_density() -> None:
    image = Image.new("RGB", (400, 800), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 220, 90), fill=(238, 118, 21))
    signal = BrandDensitySignal(
        signal_id="density",
        region=NormalizedRegion(x=0.0, y=0.0, width=0.55, height=0.28),
        target_rgb=(255, 98, 0),
        tolerance=40.0,
        min_coverage=0.33,
        min_median_red=254.0,
        max_median_blue=15.0,
        weight=1.0,
    )
    matched, _ = signal.evaluate(image)
    assert matched is False
