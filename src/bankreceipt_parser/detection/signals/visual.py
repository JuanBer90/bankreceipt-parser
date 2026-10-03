"""Visual brand-block signals (color + spatial distribution, resolution-independent)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from bankreceipt_parser.detection.signals.layout import NormalizedRegion


@dataclass(frozen=True)
class BrandBlockSignal:
    """
    Detect a compact brand color block in a normalized region.

    Matches pixels near ``target_rgb`` within ``tolerance``, then requires
    sufficient coverage in the left portion of the region and a minimum
    left/right balance (logos clustered on one side, not full-width banners).
    Optional channel constraints apply to matched pixels only.
    """

    signal_id: str
    region: NormalizedRegion
    target_rgb: tuple[int, int, int]
    tolerance: float
    min_left_coverage: float
    min_left_bias: float
    max_median_blue: float
    min_median_red: float
    weight: float
    left_width_fraction: float = 0.55

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
        mask = (luminance > 40) & (luminance < 250)
        if not mask.any():
            return False, 0.0

        target = np.array(self.target_rgb, dtype=np.float64)
        distances = np.linalg.norm(band - target, axis=2)
        color_hit = (distances <= self.tolerance) & mask

        split_x = max(1, int(band.shape[1] * self.left_width_fraction))
        left_hits = color_hit[:, :split_x]
        right_hits = color_hit[:, split_x:]

        left_mask = mask[:, :split_x]
        right_mask = mask[:, split_x:]
        left_cov = float(left_hits.sum()) / float(max(int(left_mask.sum()), 1))
        right_cov = float(right_hits.sum()) / float(max(int(right_mask.sum()), 1))
        bias = left_cov / (left_cov + right_cov + 1e-9)

        matched_pixels = band[color_hit]
        if matched_pixels.shape[0] < 30:
            return False, 0.0

        med_red = float(np.median(matched_pixels[:, 0]))
        med_blue = float(np.median(matched_pixels[:, 2]))

        if left_cov < self.min_left_coverage:
            return False, 0.0
        if bias < self.min_left_bias:
            return False, 0.0
        if med_blue > self.max_median_blue:
            return False, 0.0
        if med_red < self.min_median_red:
            return False, 0.0

        return True, self.weight


@dataclass(frozen=True)
class BrandDensitySignal:
    """
    Detect strong brand-colored coverage in a region with channel constraints.

    Complements :class:`BrandBlockSignal` when the logo spans most of the header
    band (weak left/right bias) but color purity remains distinctive.
    """

    signal_id: str
    region: NormalizedRegion
    target_rgb: tuple[int, int, int]
    tolerance: float
    min_coverage: float
    min_median_red: float
    max_median_blue: float
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
        mask = (luminance > 40) & (luminance < 250)
        if not mask.any():
            return False, 0.0

        target = np.array(self.target_rgb, dtype=np.float64)
        distances = np.linalg.norm(band - target, axis=2)
        color_hit = (distances <= self.tolerance) & mask
        coverage = float(color_hit.sum()) / float(max(int(mask.sum()), 1))
        if coverage < self.min_coverage:
            return False, 0.0

        matched_pixels = band[color_hit]
        if matched_pixels.shape[0] < 30:
            return False, 0.0

        med_red = float(np.median(matched_pixels[:, 0]))
        med_blue = float(np.median(matched_pixels[:, 2]))
        if med_red < self.min_median_red:
            return False, 0.0
        if med_blue > self.max_median_blue:
            return False, 0.0

        return True, self.weight
