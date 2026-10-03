"""Synthetic coverage for additional issuer profiles."""

from PIL import Image

from bankreceipt_parser.detection.profiles.py.bancop import BANCOP_TRANSFER_SCREEN
from bankreceipt_parser.detection.profiles.py.comecipar import COMECIPAR_TRANSFER_SUCCESS
from bankreceipt_parser.detection.profiles.py.eclub import ECLUB_TRANSFER_SCREEN
from bankreceipt_parser.detection.profiles.py.medalla_milagrosa import (
    MEDALLA_MILAGROSA_TRANSFER_OPERATION,
)
from bankreceipt_parser.detection.profiles.py.vaquita import VAQUITA_YELLOW_TRANSFER
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _ocr(lines: list[tuple[str, float]]) -> OCRResult:
    return OCRResult(
        text="\n".join(text for text, _ in lines),
        image_width=400,
        image_height=800,
        elements=[
            OCRTextElement(
                text=text,
                bbox=NormalizedBoundingBox(x=0.1, y=y, width=0.6, height=0.04),
                line_index=index,
            )
            for index, (text, y) in enumerate(lines)
        ],
    )


def test_bancop_profile_requires_visual_shell_and_ordered_copy() -> None:
    image = Image.new("RGB", (400, 800), (0, 112, 176))
    result = BANCOP_TRANSFER_SCREEN.evaluate(
        _ocr(
            [
                ("Transferencias", 0.04),
                ("Operacion realizada", 0.10),
                ("Compartir comprobante", 0.7),
            ]
        ),
        image,
    )
    assert result.accepted


def test_bancop_profile_rejects_generic_copy_without_required_visual_shell() -> None:
    result = BANCOP_TRANSFER_SCREEN.evaluate(
        _ocr(
            [
                ("Transferencias", 0.04),
                ("Operacion realizada", 0.10),
                ("Compartir comprobante", 0.7),
            ]
        ),
        None,
    )
    assert not result.accepted
    assert result.required_signals_missing == ("blue_transfer_shell",)


def test_eclub_profile_combines_shell_status_and_transfer_copy() -> None:
    image = Image.new("RGB", (400, 800), (200, 0, 64))
    result = ECLUB_TRANSFER_SCREEN.evaluate(
        _ocr([("Transferencia realizada", 0.20), ("Estado", 0.45)]), image
    )
    assert result.accepted


def test_comecipar_profile_needs_brand_and_layout_evidence() -> None:
    result = COMECIPAR_TRANSFER_SUCCESS.evaluate(
        _ocr(
            [
                ("Transferencia", 0.05),
                ("Transferencia exitosa", 0.20),
                ("Comecipar", 0.50),
                ("Transferencia", 0.90),
            ]
        ),
        None,
    )
    assert result.accepted


def test_medalla_profile_needs_brand_and_transfer_structure() -> None:
    result = MEDALLA_MILAGROSA_TRANSFER_OPERATION.evaluate(
        _ocr(
            [
                ("Transferencia operacion", 0.20),
                ("Medalla Milagrosa", 0.50),
                ("Comprobante transferencia", 0.65),
            ]
        ),
        None,
    )
    assert result.accepted


def test_vaquita_profile_needs_brand_copy_and_header_color() -> None:
    image = Image.new("RGB", (400, 800), (240, 205, 40))
    result = VAQUITA_YELLOW_TRANSFER.evaluate(
        _ocr([("Comprobante", 0.05), ("Vaquita", 0.50)]), image
    )
    assert result.accepted
