"""Geometric regularisation of per-view silhouettes.

A wobbly hand-drawn outline must be cleaned into a geometric primitive: a
near-rectangle becomes a perfect rectangle, a slight sheet tilt is removed, and
an L/T outline keeps its topology (the reflex corner of a dashed recessed
volume) while every edge becomes straight.
"""

import cv2
import numpy as np

from rhodia.config import PreprocessConfig
from rhodia.preprocessing import regularize_silhouette


def _wobbly_rect(w=400, h=300, jitter=4, seed=0) -> np.ndarray:
    """A filled rectangle whose edges wobble by a few pixels."""
    rng = np.random.default_rng(seed)
    mask = np.zeros((h, w), np.uint8)
    x0, y0, x1, y1 = 80, 60, 320, 240
    pts = []
    for x in range(x0, x1, 10):
        pts.append((x, y0 + rng.integers(-jitter, jitter + 1)))
    for y in range(y0, y1, 10):
        pts.append((x1 + rng.integers(-jitter, jitter + 1), y))
    for x in range(x1, x0, -10):
        pts.append((x, y1 + rng.integers(-jitter, jitter + 1)))
    for y in range(y1, y0, -10):
        pts.append((x0 + rng.integers(-jitter, jitter + 1), y))
    cv2.fillPoly(mask, [np.array(pts, np.int32)], 255)
    return mask


def _rectangleness(mask: np.ndarray) -> float:
    c = max(
        cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
        key=cv2.contourArea,
    )
    rect = cv2.minAreaRect(c)
    rw, rh = rect[1]
    return abs(cv2.contourArea(c)) / (rw * rh) if rw * rh else 0.0


def test_wobbly_rectangle_becomes_perfect():
    mask = _wobbly_rect()
    assert _rectangleness(mask) < 0.99  # genuinely wobbly to start
    out = regularize_silhouette(mask, PreprocessConfig())
    # After regularisation the contour fills its bounding rectangle almost fully.
    assert _rectangleness(out) > 0.995


def test_tilted_rectangle_is_derotated_to_axis_aligned():
    mask = np.zeros((300, 400), np.uint8)
    cv2.rectangle(mask, (120, 90), (300, 220), 255, -1)
    M = cv2.getRotationMatrix2D((200, 150), 6.0, 1.0)  # 6° tilt < derotate max
    tilted = cv2.warpAffine(mask, M, (400, 300), flags=cv2.INTER_NEAREST)

    out = regularize_silhouette(tilted, PreprocessConfig())
    c = max(
        cv2.findContours(out, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
        key=cv2.contourArea,
    )
    tilt = cv2.minAreaRect(c)[2] % 90.0
    tilt = min(tilt, 90.0 - tilt)
    assert tilt < 1.5  # snapped back to axis-aligned


def test_L_shape_keeps_its_topology():
    """An L outline (6 corners) must not be collapsed to a rectangle."""
    mask = np.zeros((400, 400), np.uint8)
    pts = np.array(
        [(80, 80), (320, 80), (320, 180), (180, 180), (180, 320), (80, 320)],
        np.int32,
    )
    cv2.fillPoly(mask, [pts], 255)
    out = regularize_silhouette(mask, PreprocessConfig())

    # Still an L: its area is far from filling the bounding rectangle.
    assert _rectangleness(out) < 0.75
    approx = cv2.approxPolyDP(
        max(
            cv2.findContours(out, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
            key=cv2.contourArea,
        ),
        0.02 * 1000,
        True,
    )
    assert len(approx) >= 6  # reflex corner preserved


def test_disabled_is_identity():
    mask = _wobbly_rect()
    cfg = PreprocessConfig()
    cfg.regularize_shapes = False
    out = regularize_silhouette(mask, cfg)
    assert np.array_equal(out, mask)
