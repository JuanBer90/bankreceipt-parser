"""Structured OCR results (text + spatial elements)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NormalizedBoundingBox(BaseModel):
    """Bounding box in normalized image coordinates (0.0–1.0)."""

    x: float = Field(ge=0.0, le=1.0, description="Left edge / image width.")
    y: float = Field(ge=0.0, le=1.0, description="Top edge / image height.")
    width: float = Field(ge=0.0, le=1.0)
    height: float = Field(ge=0.0, le=1.0)


class OCRTextElement(BaseModel):
    """Single OCR text unit with optional layout metadata."""

    text: str
    confidence: float | None = Field(default=None, ge=0.0, le=100.0)
    bbox: NormalizedBoundingBox
    line_index: int | None = Field(default=None, ge=0)
    block_index: int | None = Field(default=None, ge=0)
    paragraph_index: int | None = Field(default=None, ge=0)
    word_index: int | None = Field(default=None, ge=0)
    level: str = Field(default="line", description="Granularity: line or word.")


class OCRResult(BaseModel):
    """Normalized OCR text plus spatial elements from the same recognition pass."""

    text: str
    elements: list[OCRTextElement] = Field(default_factory=list)
    image_width: int = Field(ge=1)
    image_height: int = Field(ge=1)
    warnings: tuple[str, ...] = ()
