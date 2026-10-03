"""Color-region issuer profile signals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from bankreceipt_parser.detection.signals.layout import NormalizedRegion


@dataclass(frozen=True)
class ColorRegionSignal:
    """
    Score a normalized image band by fraction of pixels near a target RGB color.

    Requires ``min_coverage`` of in-band pixels (excluding near-black/near-white) to
    fall within ``tolerance`` (Euclidean distance in RGB space).
    """

    signal_id: str
    region: NormalizedRegion
    target_rgb: tuple[int, int, int]
    tolerance: float
    min_coverage: float
    weight: float

    def evaluate(self, image: Image.Image | None) -> tuple[bool, float]:
        if image is None:
            return False, 0.0

        rgb = image.convert("RGB")
        arr = np.asarray(rgb, dtype=np.float64)
        height, width = arr.shape[:2]

        x0 = max(0, int(self.region.x * width))
        y0 = max(0, int(self.region.y * height))
        x1 = min(width, int((self.region.x + self.region.width) * width))
        y1 = min(height, int((self.region.y + self.region.height) * height))
        if x1 <= x0 or y1 <= y0:
            return False, 0.0

        band = arr[y0:y1, x0:x1, :]
        luminance = band.mean(axis=2)
        mask = (luminance > 40) & (luminance < 245)
        pixels = band[mask]
        if pixels.shape[0] < 100:
            return False, 0.0

        target = np.array(self.target_rgb, dtype=np.float64)
        distances = np.linalg.norm(pixels - target, axis=1)
        coverage = float((distances <= self.tolerance).mean())
        if coverage < self.min_coverage:
            return False, 0.0
        return True, self.weight
