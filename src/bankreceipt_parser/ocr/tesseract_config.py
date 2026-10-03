"""Centralized Tesseract OCR settings."""

from __future__ import annotations

from dataclasses import dataclass

PRIMARY_LANGUAGE = "spa"
FALLBACK_LANGUAGE = "eng"

# LSTM engine. PSM 6 (uniform text block) balances line structure vs. PSM 11 (sparse text),
# which extracted more characters on local datasets but fragmented lines excessively.
DEFAULT_TESSERACT_PSM = 6
DEFAULT_TESSERACT_CONFIG = f"--oem 3 --psm {DEFAULT_TESSERACT_PSM}"

# Fully automatic page segmentation; recovers display-sized lines PSM 6 often skips.
SUPPLEMENTAL_TESSERACT_PSM = 3
SUPPLEMENTAL_TESSERACT_CONFIG = f"--oem 3 --psm {SUPPLEMENTAL_TESSERACT_PSM}"


@dataclass(frozen=True)
class TesseractLanguageChoice:
    """Resolved language pack and optional user-facing warnings."""

    lang: str
    warnings: tuple[str, ...]


def resolve_tesseract_language(available_languages: set[str]) -> TesseractLanguageChoice:
    """Prefer Spanish; use spa+eng when both exist; fall back to English or defaults."""
    if PRIMARY_LANGUAGE in available_languages:
        if FALLBACK_LANGUAGE in available_languages:
            combined = f"{PRIMARY_LANGUAGE}+{FALLBACK_LANGUAGE}"
            return TesseractLanguageChoice(lang=combined, warnings=())
        return TesseractLanguageChoice(lang=PRIMARY_LANGUAGE, warnings=())
    if FALLBACK_LANGUAGE in available_languages:
        return TesseractLanguageChoice(
            lang=FALLBACK_LANGUAGE,
            warnings=(
                "Spanish (spa) Tesseract language data is not installed; "
                "using English (eng) for OCR.",
            ),
        )
    return TesseractLanguageChoice(
        lang="",
        warnings=(
            "Neither spa nor eng Tesseract language data was found; "
            "using Tesseract default language settings.",
        ),
    )
