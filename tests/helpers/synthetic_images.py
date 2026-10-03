"""Synthetic receipt-like images with invented text."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def render_text_image(
    lines: list[str],
    *,
    width: int = 800,
    height: int = 600,
    background: str = "white",
    foreground: str = "black",
) -> bytes:
    """Build a synthetic PNG image containing invented text (no real receipt data)."""
    image = Image.new("RGB", (width, height), color=background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    y = 20
    for line in lines:
        draw.text((20, y), line, fill=foreground, font=font)
        y += 24
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def encode_jpeg(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def encode_webp(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="WEBP")
    return buffer.getvalue()
