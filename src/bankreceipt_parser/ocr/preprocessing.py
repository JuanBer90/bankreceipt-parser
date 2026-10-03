"""Image preprocessing helpers for OCR."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps

from bankreceipt_parser.ocr.images import encode_png, load_image, normalize_image_orientation


@dataclass(frozen=True)
class PreprocessOptions:
    """Tunable preprocessing strategy (conservative defaults for receipt photos)."""

    # Upscale only genuinely low-resolution inputs; phone screenshots are often >= 1080px.
    min_side_px: int = 480
    max_side_px: int = 4000
    upscale_interpolation: int = cv2.INTER_CUBIC
    apply_clahe: bool = True
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: int = 8


def preprocess_image(
    image: Image.Image,
    options: PreprocessOptions | None = None,
    *,
    assume_oriented: bool = False,
) -> Image.Image:
    """
    Prepare a receipt image for OCR.

    Applies grayscale, optional mild CLAHE contrast, and upscales small images so
    Tesseract receives enough resolution. Standalone callers receive EXIF-orientation
    normalization; the pipeline passes an already oriented image explicitly.
    """
    opts = options or PreprocessOptions()
    oriented = image if assume_oriented else normalize_image_orientation(image)
    rgb = oriented.convert("RGB")
    gray = ImageOps.grayscale(rgb)

    width, height = gray.size
    short_side = min(width, height)
    long_side = max(width, height)

    if short_side < opts.min_side_px:
        scale = opts.min_side_px / short_side
        new_w = round(width * scale)
        new_h = round(height * scale)
        gray = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

    width, height = gray.size
    long_side = max(width, height)
    if long_side > opts.max_side_px:
        scale = opts.max_side_px / long_side
        new_w = round(width * scale)
        new_h = round(height * scale)
        gray = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

    if opts.apply_clahe:
        gray = _apply_clahe(gray, opts)

    return gray


def preprocess_for_ocr(image: bytes, options: PreprocessOptions | None = None) -> bytes:
    """Load PNG/JPEG/WEBP bytes, preprocess, and return PNG bytes for an OCR engine."""
    loaded, _fmt = load_image(image)
    oriented = normalize_image_orientation(loaded)
    processed = preprocess_image(oriented, options, assume_oriented=True)
    return encode_png(processed)


def _apply_clahe(image: Image.Image, options: PreprocessOptions) -> Image.Image:
    array = np.array(image)
    clahe = cv2.createCLAHE(
        clipLimit=options.clahe_clip_limit,
        tileGridSize=(options.clahe_tile_grid_size, options.clahe_tile_grid_size),
    )
    enhanced = clahe.apply(array)
    return Image.fromarray(enhanced, mode="L")


def preprocess_image_to_bytes(
    image: Image.Image,
    options: PreprocessOptions | None = None,
) -> bytes:
    """Preprocess a PIL image and encode as PNG bytes."""
    return encode_png(preprocess_image(image, options))


def decode_png_bytes(image: bytes) -> Image.Image:
    """Decode PNG bytes to a PIL image (used by OCR engines)."""
    with Image.open(BytesIO(image)) as opened:
        return opened.copy()
