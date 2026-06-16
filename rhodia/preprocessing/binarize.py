"""Extract pencil strokes from a (de-gridded) grayscale image and binarise."""

from __future__ import annotations

import cv2
import numpy as np

from ..config import PreprocessConfig


def extract_pencil(gray: np.ndarray, cfg: PreprocessConfig | None = None) -> np.ndarray:
    """Return a clean binary stroke image (uint8, 255 = ink, 0 = paper).

    Pencil graphite has low, spatially-varying contrast, so a global threshold
    is unreliable.  We use:
      * CLAHE to normalise local contrast,
      * adaptive (Gaussian) thresholding to isolate dark strokes,
      * morphological opening + small-blob removal to drop paper speckle.
    """
    cfg = cfg or PreprocessConfig()

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    norm = clahe.apply(gray)

    block = cfg.pencil_block_size | 1  # must be odd
    binary = cv2.adaptiveThreshold(
        norm,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        cfg.pencil_C,
    )

    # Remove isolated noise, then bridge tiny gaps in strokes.
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    binary = _drop_small_components(binary, min_area=20)
    return binary


def _drop_small_components(binary: np.ndarray, min_area: int) -> np.ndarray:
    """Zero-out connected components smaller than *min_area* pixels."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    out = np.zeros_like(binary)
    for i in range(1, n):  # 0 = background
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 255
    return out
