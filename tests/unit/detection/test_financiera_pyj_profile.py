"""FINANCIERA PYJ detection profile tests (synthetic OCR only)."""

from bankreceipt_parser.detection.profiles.py.financiera_pyj import FINANCIERA_PYJ_TRANSFER_RECEIPT
from bankreceipt_parser.ocr.structure import NormalizedBoundingBox, OCRResult, OCRTextElement


def _ocr(lines: list[str]) -> OCRResult:
    return OCRResult(
        text="\n".join(lines),
        image_width=400,
        image_height=900,
        elements=[
            OCRTextElement(
                text=line,
                bbox=NormalizedBoundingBox(x=0.1, y=0.05 + index * 0.04, width=0.8, height=0.03),
                line_index=index,
            )
            for index, line in enumerate(lines)
        ],
    )


def test_financiera_pyj_transfer_profile_accepts_synthetic_receipt() -> None:
    result = FINANCIERA_PYJ_TRANSFER_RECEIPT.evaluate(
        _ocr(
            [
                "FINANCIERA",
                "Comprobante de Transferencia",
                "Cuenta debito: 100001",
                "Nombre del Titular TITULAR EJEMPLO",
                "NTR: FIPJPYPAARES000000001",
            ]
        ),
        None,
    )
    assert result.accepted


def test_financiera_pyj_profile_rejects_generic_transfer_without_structure() -> None:
    result = FINANCIERA_PYJ_TRANSFER_RECEIPT.evaluate(
        _ocr(["Comprobante de Transferencia", "FINANCIERA"]),
        None,
    )
    assert not result.accepted
