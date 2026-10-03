"""Tests for OCR preprocessing."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from bankreceipt_parser.ocr.preprocessing import (
    PreprocessOptions,
    preprocess_for_ocr,
    preprocess_image,
)


def test_preprocess_preserves_readable_image() -> None:
    source = Image.new("RGB", (1200, 800), color=(240, 240, 240))
    processed = preprocess_image(source)
    assert processed.mode == "L"
    assert processed.size[0] >= 900


def test_preprocess_upscales_small_images() -> None:
    source = Image.new("RGB", (200, 300), color="white")
    processed = preprocess_image(source, PreprocessOptions(min_side_px=900))
    assert min(processed.size) == 900


def test_preprocess_is_deterministic() -> None:
    source = Image.new("RGB", (640, 480), color=(128, 128, 128))
    first = preprocess_image(source)
    second = preprocess_image(source)
    assert first.tobytes() == second.tobytes()


def test_preprocess_applies_exif_orientation() -> None:
    # Landscape content stored with orientation tag requiring transpose.
    source = Image.new("RGB", (100, 200), color="white")
    exif = source.getexif()
    exif[274] = 6  # EXIF orientation: rotate 90 CW
    buffer = BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    buffer.seek(0)
    opts = PreprocessOptions(min_side_px=1, max_side_px=10000, apply_clahe=False)
    with Image.open(buffer) as loaded:
        processed = preprocess_image(loaded, opts)
    assert processed.size == (200, 100)


def test_preprocess_for_ocr_bytes_roundtrip() -> None:
    image = Image.new("RGB", (500, 500), color="white")
    buf = BytesIO()
    image.save(buf, format="PNG")
    out = preprocess_for_ocr(buf.getvalue())
    assert out.startswith(b"\x89PNG")
