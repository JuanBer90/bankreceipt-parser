"""Load and validate receipt images (in-memory only)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageOps, UnidentifiedImageError

from bankreceipt_parser.exceptions import ImageLoadError, ImageTooLargeError, UnsupportedImageError

if TYPE_CHECKING:
    from typing import Literal

ImageSource = str | Path | bytes

SUPPORTED_FORMATS: frozenset[str] = frozenset({"PNG", "JPEG", "WEBP"})
# Covers common high-resolution phone photos while bounding decode-time memory use.
MAX_IMAGE_PIXELS = 50_000_000


def load_image(source: ImageSource) -> tuple[Image.Image, Literal["PNG", "JPEG", "WEBP"]]:
    """Load a PNG, JPEG, or WEBP image from a path or raw bytes."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise ImageLoadError(f"Image file does not exist: {path}")
        try:
            with Image.open(path) as opened:
                image, fmt = _copy_validated_image(opened)
        except UnidentifiedImageError as exc:
            raise UnsupportedImageError(f"Unsupported or corrupt image: {path}") from exc
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageTooLargeError("Image exceeds Pillow's decompression-bomb limit.") from exc
        except OSError as exc:
            raise UnsupportedImageError(f"Could not read image: {path}") from exc
        return image, fmt

    if not source:
        raise ImageLoadError("Image bytes are empty.")

    try:
        with Image.open(BytesIO(source)) as opened:
            image, fmt = _copy_validated_image(opened)
    except UnidentifiedImageError as exc:
        raise UnsupportedImageError("Unsupported or corrupt image bytes.") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageTooLargeError("Image exceeds Pillow's decompression-bomb limit.") from exc
    except OSError as exc:
        raise UnsupportedImageError("Could not decode image bytes.") from exc

    return image, fmt


def normalize_image_orientation(image: Image.Image) -> Image.Image:
    """Return a correctly oriented, independent image for the processing pipeline."""
    return ImageOps.exif_transpose(image)


def _copy_validated_image(
    opened: Image.Image,
) -> tuple[Image.Image, Literal["PNG", "JPEG", "WEBP"]]:
    fmt = _validated_format(opened.format)
    _validate_image_dimensions(*opened.size)
    return opened.copy(), fmt


def _validate_image_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ImageLoadError("Image dimensions must be positive.")
    pixels = width * height
    if pixels > MAX_IMAGE_PIXELS:
        raise ImageTooLargeError(
            f"Image has {pixels:,} pixels; maximum supported size is {MAX_IMAGE_PIXELS:,}."
        )


def _validated_format(raw_format: str | None) -> Literal["PNG", "JPEG", "WEBP"]:
    if raw_format is None:
        raise UnsupportedImageError("Could not determine image format.")
    normalized = raw_format.upper()
    if normalized == "JPG":
        normalized = "JPEG"
    if normalized not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise UnsupportedImageError(
            f"Unsupported image format {raw_format!r}. Supported formats: {supported}."
        )
    return normalized  # type: ignore[return-value]


def encode_png(image: Image.Image) -> bytes:
    """Encode an image as PNG bytes (in memory)."""
    buffer = BytesIO()
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    image.save(buffer, format="PNG")
    return buffer.getvalue()
