"""Extract pencil strokes from a (de-gridded) grayscale image and binarise.

Two methods are available:

* **strength** (default) — isolate pencil by *contrast strength*: how much darker
  a pixel is than the local paper background (estimated by morphological
  closing).  The printed Rhodia quadrille is light (barely darker than paper)
  while pencil is strongly dark, so a strength floor rejects the grid yet keeps
  every dark stroke — including the dashed/hidden edges used to draw recessed
  volumes.  This is robust on faint-grid scans where a local adaptive threshold
  would otherwise lock onto the grid itself.
* **adaptive** (legacy, ``pencil_min_strength = 0``) — CLAHE + adaptive Gaussian
  threshold.  Kept for high-contrast scans with no residual grid.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import PreprocessConfig


def _min_component_area(shape: tuple[int, int]) -> int:
    """Speckle-removal floor, scaled to the image so it works at any resolution."""
    h, w = shape[:2]
    return max(20, int(h * w * 1.2e-5))


def _extract_by_strength(gray: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """Binarise by contrast strength against the local paper background."""
    k = int(cfg.pencil_bg_kernel) | 1  # odd
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    deficit = cv2.subtract(background, gray)  # >0 where darker than paper
    # grid_tolerance raises the floor (removes more faint structure).
    strength = max(1, int(round(cfg.pencil_min_strength + cfg.grid_tolerance * 8)))
    return ((deficit >= strength) * 255).astype(np.uint8)


def _extract_by_adaptive(gray: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """Legacy CLAHE + adaptive-threshold binarisation."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    norm = clahe.apply(gray)
    block = cfg.pencil_block_size | 1  # must be odd
    return cv2.adaptiveThreshold(
        norm,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        cfg.pencil_C,
    )


def extract_pencil(gray: np.ndarray, cfg: PreprocessConfig | None = None) -> np.ndarray:
    """Return a clean binary stroke image (uint8, 255 = ink, 0 = paper)."""
    cfg = cfg or PreprocessConfig()

    if cfg.pencil_min_strength > 0:
        binary = _extract_by_strength(gray, cfg)
    else:
        binary = _extract_by_adaptive(gray, cfg)

    # Remove isolated noise, then bridge tiny gaps in strokes.
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    binary = _drop_small_components(binary, _min_component_area(gray.shape))
    return binary


def _drop_small_components(binary: np.ndarray, min_area: int) -> np.ndarray:
    """Zero-out connected components smaller than *min_area* pixels."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    out = np.zeros_like(binary)
    for i in range(1, n):  # 0 = background
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 255
    return out
