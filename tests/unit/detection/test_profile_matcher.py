"""Issuer profile and signal tests (synthetic OCR/images only)."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from bankreceipt_parser.detection.heuristics import detect_issuer_from_ocr
from bankreceipt_parser.detection.matcher import best_profile_match, evaluate_profiles
from bankreceipt_parser.detection.outcome import DetectionStatus
from bankreceipt_parser.detection.profile import IssuerProfile
from bankreceipt_parser.detection.profiles.py.ueno import (
    UENO_MOVEMENT_DETAIL,
    UENO_PAYMENT_RECEIPT,
    UENO_TRANSFER_SUMMARY,
)
from bankreceipt_parser.detection.signals.color import ColorRegionSignal
from bankreceipt_parser.detection.signals.layout import NormalizedRegion
from bankreceipt_parser.detection.signals.product_lexicon import _normalized_term_matches_text
from bankreceipt_parser.detection.signals.text import TextSignal
from bankreceipt_parser.models.issuer import Issuer
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement
from bankreceipt_parser.parsers.py.ueno import UenoVariant


def _element(text: str, y: float, x: float = 0.1) -> OCRTextElement:
    return OCRTextElement(
        text=text,
        bbox=NormalizedBoundingBox(x=x, y=y, width=0.3, height=0.04),
        line_index=1,
    )


def _mint_header_image(*, width: int = 400, height: int = 800) -> Image.Image:
    image = Image.new("RGB", (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(image)
    header_h = int(0.35 * height)
    draw.rectangle((0, 0, width, header_h), fill=(122, 245, 191))
    font = ImageFont.load_default()
    draw.text((40, int(0.18 * height)), "Transferiste Gs.", fill="black", font=font)
    draw.text((40, int(0.34 * height)), "Detalle de tu transferencia", fill="black", font=font)
    draw.text((40, int(0.47 * height)), "Cuenta destino", fill="black", font=font)
    draw.text((40, int(0.54 * height)), "Entidad", fill="black", font=font)
    return image


def _ocr_for_ueno_like_summary() -> OCRResult:
    return OCRResult(
        text=(
            "Transferiste Gs.\nDetalle de tu transferencia\n"
            "Cuenta destino\nEntidad\nReferencia inventada"
        ),
        image_width=400,
        image_height=800,
        elements=[
            _element("Transferiste", 0.20, 0.25),
            _element("Detalle", 0.34, 0.10),
            _element("transferencia", 0.34, 0.32),
            _element("Cuenta", 0.47, 0.10),
            _element("destino", 0.47, 0.21),
            _element("Entidad", 0.54, 0.10),
        ],
    )


def test_text_signal_scores_normalized_phrase_in_region() -> None:
    ocr = _ocr_for_ueno_like_summary()
    signal = TextSignal(
        signal_id="transferiste",
        phrases=("transferiste",),
        weight=1.0,
        region=NormalizedRegion(x=0.0, y=0.12, width=1.0, height=0.22),
    )
    matched, score = signal.evaluate(ocr)
    assert matched is True
    assert score == 1.0


def test_text_signal_region_rejects_out_of_band_placement() -> None:
    ocr = OCRResult(
        text="Transferiste",
        image_width=100,
        image_height=100,
        elements=[_element("Transferiste", 0.75)],
    )
    signal = TextSignal(
        signal_id="transferiste",
        phrases=("transferiste",),
        weight=1.0,
        region=NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.3),
    )
    matched, score = signal.evaluate(ocr)
    assert matched is False
    assert score == 0.0


def test_color_region_signal_respects_tolerance() -> None:
    image = _mint_header_image()
    strong = ColorRegionSignal(
        signal_id="mint",
        region=NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.35),
        target_rgb=(122, 245, 191),
        tolerance=55.0,
        min_coverage=0.5,
        weight=1.2,
    )
    weak = ColorRegionSignal(
        signal_id="mint",
        region=NormalizedRegion(x=0.0, y=0.0, width=1.0, height=0.35),
        target_rgb=(20, 20, 20),
        tolerance=5.0,
        min_coverage=0.5,
        weight=1.2,
    )
    ok_strong, score_strong = strong.evaluate(image)
    ok_weak, score_weak = weak.evaluate(image)
    assert ok_strong and score_strong == 1.2
    assert not ok_weak and score_weak == 0.0


def test_profile_aggregation_and_minimum_threshold() -> None:
    ocr = _ocr_for_ueno_like_summary()
    image = _mint_header_image()
    result = UENO_TRANSFER_SUMMARY.evaluate(ocr, image)
    assert result.score >= UENO_TRANSFER_SUMMARY.min_score
    assert len(result.matched_signals) >= 4


def test_best_profile_unknown_when_below_min_score() -> None:
    ocr = OCRResult(text="hola", image_width=10, image_height=10, elements=[])
    results = evaluate_profiles(ocr, None, (UENO_TRANSFER_SUMMARY,))
    assert best_profile_match(results) is None


def test_profile_ambiguity_requires_margin_between_profiles() -> None:
    near_duplicate = IssuerProfile(
        issuer=Issuer.UENO,
        variant="alt",
        min_score=1.0,
        signals=(
            TextSignal(signal_id="a", phrases=("transferiste",), weight=2.0),
            TextSignal(signal_id="b", phrases=("detalle",), weight=1.9),
        ),
    )
    twin = IssuerProfile(
        issuer=Issuer.UENO,
        variant="alt2",
        min_score=1.0,
        signals=(
            TextSignal(signal_id="c", phrases=("transferiste",), weight=2.0),
            TextSignal(signal_id="d", phrases=("entidad",), weight=1.85),
        ),
    )
    ocr = _ocr_for_ueno_like_summary()
    results = evaluate_profiles(ocr, None, (near_duplicate, twin))
    assert best_profile_match(results, min_margin=0.5) is None


def test_exclusion_veto_on_comprobante_transferencia_upper() -> None:
    ocr = OCRResult(
        text="Comprobante de transferencia\nTransferiste",
        image_width=100,
        image_height=200,
        elements=[
            _element("Comprobante de transferencia", 0.08),
            _element("Transferiste", 0.20),
        ],
    )
    image = _mint_header_image()
    result = UENO_TRANSFER_SUMMARY.evaluate(ocr, image)
    assert result.vetoed is True


def test_synthetic_ueno_transfer_summary_detection() -> None:
    ocr = _ocr_for_ueno_like_summary()
    image = _mint_header_image()
    outcome = detect_issuer_from_ocr(ocr, image=image)
    assert outcome.status == DetectionStatus.IDENTIFIED
    assert outcome.issuer == Issuer.UENO
    assert outcome.variant == UenoVariant.TRANSFER_SUMMARY
    assert outcome.score is not None and outcome.score >= 3.4


def test_similar_non_ueno_does_not_match_profile() -> None:
    """Green header + generic transfer words but not UENO transfer-summary layout."""
    image = Image.new("RGB", (400, 800), color=(250, 250, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 400, 280), fill=(122, 245, 191))
    font = ImageFont.load_default()
    draw.text((40, 120), "Comprobante de transferencia", fill="black", font=font)
    draw.text((40, 200), "Monto total", fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    ocr = OCRResult(
        text="Comprobante de transferencia\nMonto total",
        image_width=400,
        image_height=800,
        elements=[
            _element("Comprobante de transferencia", 0.08),
            _element("Monto", 0.25),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr, image=Image.open(buffer))
    assert outcome.issuer != Issuer.UENO or outcome.variant != "transfer_summary"


def _ocr_for_ueno_payment_receipt() -> OCRResult:
    return OCRResult(
        text=(
            "Comprobante de pago\nNro. de comprobante: 0000001\n"
            "Cuenta destino\nCuenta origen\nEntidad origen\nMarca inventada ueno bank"
        ),
        image_width=400,
        image_height=800,
        elements=[
            _element("Comprobante de pago", 0.12),
            _element("Nro. de comprobante:", 0.18),
            _element("Cuenta destino", 0.50),
            _element("Cuenta origen", 0.58),
            _element("Entidad origen", 0.66),
            _element("ueno bank", 0.72),
        ],
    )


def test_strong_issuer_text_ueno_bank_resolves_issuer() -> None:
    ocr = _ocr_for_ueno_payment_receipt()
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer == Issuer.UENO
    assert outcome.score is not None and outcome.score >= 1.2


def test_payment_receipt_variant_when_issuer_and_format_match() -> None:
    ocr = _ocr_for_ueno_payment_receipt()
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.variant == "payment_receipt"
    assert outcome.method == "text+profile"


def test_payment_receipt_not_confused_with_transfer_summary() -> None:
    ocr = _ocr_for_ueno_payment_receipt()
    image = _mint_header_image()
    pay = UENO_PAYMENT_RECEIPT.evaluate(ocr, image)
    summary = UENO_TRANSFER_SUMMARY.evaluate(ocr, image)
    assert pay.accepted is True
    assert summary.accepted is False


def test_insufficient_evidence_stays_unknown() -> None:
    ocr = OCRResult(
        text="Comprobante genérico sin marca",
        image_width=100,
        image_height=100,
        elements=[_element("Comprobante", 0.1)],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.UNKNOWN


def test_ueno_bank_matches_ocr_split_legal_suffix() -> None:
    assert _normalized_term_matches_text("ueno bank", "entidad origen ueno s.a. bank moneda")
    assert not _normalized_term_matches_text("ueno bank", "banco continental paraguay")


def test_issuer_resolution_ueno_bank_sa_synthetic() -> None:
    ocr = OCRResult(
        text="Detalle de movimiento\nEntidad origen UENO S.A. BANK",
        image_width=100,
        image_height=400,
        elements=[
            _element("Detalle de movimiento", 0.08),
            _element("UENO", 0.70),
            _element("S.A.", 0.70, x=0.3),
            _element("BANK", 0.70, x=0.5),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer == Issuer.UENO
    assert outcome.score is not None and outcome.score >= 1.2


def test_movement_detail_variant_synthetic() -> None:
    ocr = OCRResult(
        text=(
            "Detalle de movimiento\nDetalle de la transferencia\n"
            "Transferencia enviada\nMonto\nConcepto\nEntidad origen\n"
            "Nro. de comprobante\nMarca ueno s.a. bank"
        ),
        image_width=100,
        image_height=600,
        elements=[
            _element("Detalle de movimiento", 0.06),
            _element("Detalle de la transferencia", 0.14),
            _element("enviada", 0.22),
            _element("Monto", 0.30),
            _element("Concepto", 0.34),
            _element("Entidad origen", 0.50),
            _element("Nro. de comprobante", 0.58),
            _element("ueno bank", 0.72),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.variant == "movement_detail"


def test_movement_detail_not_confused_with_payment_or_transfer_summary() -> None:
    ocr = OCRResult(
        text=(
            "Detalle de movimiento\nDetalle de la transferencia\n"
            "Monto\nConcepto\nEntidad origen\nueno s.a. bank"
        ),
        image_width=100,
        image_height=500,
        elements=[
            _element("Detalle de movimiento", 0.06),
            _element("Detalle de la transferencia", 0.14),
            _element("Monto", 0.30),
            _element("Concepto", 0.34),
            _element("Entidad origen", 0.50),
            _element("ueno", 0.72),
        ],
    )
    pay = UENO_PAYMENT_RECEIPT.evaluate(ocr, None)
    move = UENO_MOVEMENT_DETAIL.evaluate(ocr, None)
    summary = UENO_TRANSFER_SUMMARY.evaluate(ocr, None)
    assert move.accepted is True
    assert pay.vetoed is True
    assert summary.accepted is False


def test_movimiento_without_ueno_brand_stays_unknown() -> None:
    ocr = OCRResult(
        text="Detalle de movimiento\nMonto\nConcepto",
        image_width=100,
        image_height=300,
        elements=[
            _element("Detalle de movimiento", 0.1),
            _element("Monto", 0.3),
            _element("Concepto", 0.4),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.status == DetectionStatus.UNKNOWN
    assert outcome.issuer != Issuer.UENO


def test_generic_payment_text_without_ueno_not_classified_as_ueno() -> None:
    ocr = OCRResult(
        text="Comprobante de pago\nCuenta destino\nCuenta origen\nEntidad origen",
        image_width=100,
        image_height=400,
        elements=[
            _element("Comprobante de pago", 0.1),
            _element("Cuenta destino", 0.3),
            _element("Cuenta origen", 0.4),
            _element("Entidad origen", 0.5),
        ],
    )
    outcome = detect_issuer_from_ocr(ocr)
    assert outcome.issuer != Issuer.UENO


def test_text_signal_match_all_requires_every_phrase() -> None:
    ocr = OCRResult(
        text="Detalle solamente",
        image_width=100,
        image_height=100,
        elements=[_element("Detalle", 0.34)],
    )
    signal = TextSignal(
        signal_id="detalle_transferencia",
        phrases=("detalle", "transferencia"),
        weight=1.0,
        region=NormalizedRegion(x=0.0, y=0.28, width=1.0, height=0.2),
        match_all=True,
    )
    matched, _ = signal.evaluate(ocr)
    assert matched is False
