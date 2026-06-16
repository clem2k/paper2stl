"""Geometry primitives shared across preprocessing and reconstruction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Segment:
    """A straight 2D segment in image pixel coordinates (origin top-left)."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def length(self) -> float:
        return float(np.hypot(self.x2 - self.x1, self.y2 - self.y1))

    @property
    def angle(self) -> float:
        """Orientation in radians, folded to [0, pi)."""
        a = np.arctan2(self.y2 - self.y1, self.x2 - self.x1)
        return float(a % np.pi)

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def as_array(self) -> np.ndarray:
        return np.array([self.x1, self.y1, self.x2, self.y2], dtype=np.float64)


def angular_distance(a: float, b: float) -> float:
    """Smallest distance between two undirected line angles in [0, pi)."""
    d = abs(a - b) % np.pi
    return min(d, np.pi - d)


def point_line_distance(px: float, py: float, seg: Segment) -> float:
    """Perpendicular distance from a point to the *infinite* line of ``seg``."""
    x1, y1, x2, y2 = seg.x1, seg.y1, seg.x2, seg.y2
    num = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1)
    den = np.hypot(y2 - y1, x2 - x1) + 1e-9
    return float(num / den)


def normalize_unit_square(points: np.ndarray) -> tuple[np.ndarray, dict]:
    """Map an (N,2) point set into the unit square, preserving aspect ratio.

    Returns the transformed points and the affine parameters (scale, offset)
    so the mapping can be inverted / shared across views for registration.
    """
    pts = np.asarray(points, dtype=np.float64)
    mn = pts.min(axis=0)
    mx = pts.max(axis=0)
    span = (mx - mn).max() + 1e-9
    out = (pts - mn) / span
    return out, {"min": mn, "span": span}
