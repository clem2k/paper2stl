"""Faint-grid removal and dashed (hidden-edge) line handling.

A recessed volume — visible from a face but not touching its plane — is drawn
with dashed lines.  For the visual hull the silhouette must be the *union* of
the solid and dashed outlines, so the dashes have to survive grid removal and be
bridged into complete edges that the flood-fill can enclose.
"""

import cv2
import numpy as np

from rhodia.config import PreprocessConfig
from rhodia.preprocessing import extract_pencil, remove_grid, vectorize_lines
from rhodia.preprocessing.vectorize import rasterize_silhouette


def _synthetic_scan() -> np.ndarray:
    """A faint blue quadrille with a solid box and a dashed box stacked above."""
    h, w = 900, 700
    img = np.full((h, w, 3), 250, np.uint8)  # near-white paper

    # Faint light-blue grid (high value, low saturation → barely chromatic).
    grid_color = (244, 236, 228)  # BGR: slightly blue, light
    for x in range(0, w, 30):
        cv2.line(img, (x, 0), (x, h), grid_color, 1)
    for y in range(0, h, 30):
        cv2.line(img, (0, y), (w, y), grid_color, 1)

    dark = (40, 40, 40)
    # Solid rectangle (touches the plane) at the bottom.
    cv2.rectangle(img, (200, 560), (500, 760), dark, 4)
    # Dashed rectangle (recessed volume) stacked above, sharing the top edge.
    x0, x1, y0, y1 = 200, 500, 320, 560
    for x in range(x0, x1, 80):  # dashes ~50px with ~30px gaps
        cv2.line(img, (x, y0), (min(x + 50, x1), y0), dark, 4)
        cv2.line(img, (x, y1), (min(x + 50, x1), y1), dark, 4)
    for y in range(y0, y1, 80):
        cv2.line(img, (x0, y), (x0, min(y + 50, y1)), dark, 4)
        cv2.line(img, (x1, y), (x1, min(y + 50, y1)), dark, 4)
    return img


def test_strength_binarization_removes_faint_grid():
    img = _synthetic_scan()
    cfg = PreprocessConfig()  # strength method on by default
    gray = remove_grid(img, cfg)
    binary = extract_pencil(gray, cfg)
    # The drawing is a thin outline: ink must be a small fraction, i.e. the grid
    # is gone (a retained grid would push this well above 10%).
    assert (binary > 0).mean() < 0.05


def test_dashed_region_is_filled_in_silhouette():
    img = _synthetic_scan()
    cfg = PreprocessConfig()
    gray = remove_grid(img, cfg)
    binary = extract_pencil(gray, cfg)
    segments = vectorize_lines(binary, cfg)
    sil = rasterize_silhouette(segments, binary.shape, thickness=3)

    # Centre of the DASHED rectangle must be filled — the recessed volume is
    # part of the silhouette, not lost to the dash gaps.
    assert sil[440, 350] > 0
    # Centre of the solid rectangle is filled too.
    assert sil[660, 350] > 0
    # A corner well outside both boxes stays empty (grid did not leak in).
    assert sil[60, 60] == 0
    # And the fill is a sensible region, not a total flood-fill leak.
    assert 0.05 < (sil > 0).mean() < 0.6


def test_legacy_adaptive_method_still_available():
    img = _synthetic_scan()
    cfg = PreprocessConfig()
    cfg.pencil_min_strength = 0  # fall back to adaptive threshold
    gray = remove_grid(img, cfg)
    binary = extract_pencil(gray, cfg)
    assert binary.shape == gray.shape
    assert binary.dtype == np.uint8
