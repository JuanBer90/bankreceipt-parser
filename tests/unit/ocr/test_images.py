"""Tests for image loading and validation."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from bankreceipt_parser.exceptions import ImageLoadError, ImageTooLargeError, UnsupportedImageError
from bankreceipt_parser.ocr.images import MAX_IMAGE_PIXELS, _validate_image_dimensions, load_image
from helpers.synthetic_images import encode_jpeg, encode_webp, render_text_image


def test_load_image_from_path_str(tmp_path: Path) -> None:
    png_path = tmp_path / "sample.png"
    png_path.write_bytes(render_text_image(["Hola"]))
    image, fmt = load_image(str(png_path))
    assert fmt == "PNG"
    assert image.size[0] > 0


def test_load_image_from_path(tmp_path: Path) -> None:
    png_path = tmp_path / "sample.png"
    png_path.write_bytes(render_text_image(["Hola"]))
    _image, fmt = load_image(png_path)
    assert fmt == "PNG"


def test_load_image_from_bytes() -> None:
    data = render_text_image(["bytes input"])
    _image, fmt = load_image(data)
    assert fmt == "PNG"


def test_load_image_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ImageLoadError, match="does not exist"):
        load_image(tmp_path / "missing.png")


def test_load_image_empty_bytes() -> None:
    with pytest.raises(ImageLoadError, match="empty"):
        load_image(b"")


def test_load_image_corrupt_bytes() -> None:
    with pytest.raises(UnsupportedImageError, match="corrupt"):
        load_image(b"not-a-real-image")


def test_load_image_unsupported_gif_bytes() -> None:
    image = Image.new("RGB", (10, 10), "red")
    buffer = BytesIO()
    image.save(buffer, format="GIF")
    with pytest.raises(UnsupportedImageError, match="Unsupported image format"):
        load_image(buffer.getvalue())


def test_load_image_jpeg_and_webp() -> None:
    base = Image.new("RGB", (40, 40), "white")
    _img, fmt_j = load_image(encode_jpeg(base))
    assert fmt_j == "JPEG"
    _img, fmt_w = load_image(encode_webp(base))
    assert fmt_w == "WEBP"


def test_rejects_dimensions_over_explicit_limit_without_large_fixture() -> None:
    with pytest.raises(ImageTooLargeError, match="maximum supported size"):
        _validate_image_dimensions(MAX_IMAGE_PIXELS + 1, 1)


def test_rejects_extreme_dimensions_without_allocating_image() -> None:
    with pytest.raises(ImageTooLargeError):
        _validate_image_dimensions(100_000, 100_000)


def test_wraps_pillow_decompression_bomb_as_domain_error() -> None:
    with patch(
        "bankreceipt_parser.ocr.images.Image.open",
        side_effect=Image.DecompressionBombError("synthetic bomb"),
    ), pytest.raises(ImageTooLargeError, match="decompression-bomb"):
        load_image(b"synthetic")
