"""Aggressive geometric regularisation of a per-view filled silhouette.

Even after the wireframe is TLS-straightened, the *filled silhouette* still has
slightly wobbly edges and off-by-a-degree corners.  The visual hull then turns
those into waves on what should be perfectly flat faces.  Here we clean the
silhouette as a geometric primitive:

* a **near-rectangular** outline is collapsed to a perfect rectangle, so a shape
  that looks ~95% like a square on every sheet yields a perfect box;
* otherwise every polygon edge is **snapped** to the dominant orientation (and
  its 45/90/135° relatives) when close enough, and corners are recomputed as
  exact edge intersections — genuine slopes are kept, and the L/T topology of a
  dashed recessed volume (its reflex corner) is preserved;
* a small residual **sheet tilt** is removed first so the part is axis-aligned,
  which is what makes the carved box come out square (an intentional larger
  rotation is left untouched).

The input and output are both filled binary silhouettes (uint8, 255 = part).
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import PreprocessConfig


def _poly_area(verts: np.ndarray) -> float:
    """Absolute area of a polygon given as an ``(N, 2)`` vertex array."""
    x, y = verts[:, 0], verts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _minrect_tilt_deg(rect) -> float:
    """Tilt of a ``cv2.minAreaRect`` mapped to ``[-45, 45]`` degrees."""
    a = rect[2] % 90.0
    return a - 90.0 if a > 45.0 else a


def _global_tilt(contours: list[np.ndarray], max_deg: float) -> float:
    """Small in-plane tilt (deg) to remove so the part becomes axis-aligned.

    Uses the largest contour's min-area rectangle; returns 0 when the tilt
    exceeds ``max_deg`` (treated as an intentional rotation, left untouched).
    """
    if max_deg <= 0:
        return 0.0
    c = max(contours, key=cv2.contourArea)
    tilt = _minrect_tilt_deg(cv2.minAreaRect(c))
    return tilt if abs(tilt) <= max_deg else 0.0


def _derotate(mask: np.ndarray, deg: float) -> np.ndarray:
    """Rotate *mask* by ``-deg`` about its centre (nearest-neighbour, binary)."""
    if deg == 0.0:
        return mask
    h, w = mask.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), deg, 1.0)
    return cv2.warpAffine(
        mask, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0
    )


def _snap_angle(a: float, theta: float, tol: float) -> float:
    """Snap angle *a* (rad) to ``theta + k·45°`` if within *tol* (rad); else *a*."""
    best, best_d = a, tol
    for k in range(4):
        cand = theta + k * (np.pi / 4.0)
        # signed angular difference modulo pi, folded into [-pi/2, pi/2]
        d = (a - cand + np.pi / 2.0) % np.pi - np.pi / 2.0
        if abs(d) < best_d:
            best, best_d = cand, abs(d)
    return best


def _line_intersection(p1, d1, p2, d2):
    """Intersection of lines ``p1 + t·d1`` and ``p2 + s·d2``; None if parallel."""
    a = np.array([[d1[0], -d2[0]], [d1[1], -d2[1]]], dtype=np.float64)
    if abs(np.linalg.det(a)) < 1e-6:
        return None
    t = np.linalg.solve(a, np.asarray(p2, float) - np.asarray(p1, float))[0]
    return np.asarray(p1, float) + t * np.asarray(d1, float)


def _regularize_contour(
    contour: np.ndarray, cfg: PreprocessConfig
) -> np.ndarray | None:
    """Return regularised vertices for one contour, or None to keep it as-is."""
    peri = cv2.arcLength(contour, True)
    eps = max(1.0, cfg.regularize_poly_epsilon_frac * peri)
    approx = cv2.approxPolyDP(contour, eps, True).reshape(-1, 2).astype(np.float64)
    n = len(approx)
    if n < 3:
        return None

    theta = np.deg2rad(cv2.minAreaRect(contour)[2] % 180.0)
    snap_tol = np.deg2rad(cfg.regularize_angle_snap_deg)

    mids, dirs = [], []
    for i in range(n):
        p, q = approx[i], approx[(i + 1) % n]
        ang = _snap_angle(np.arctan2(q[1] - p[1], q[0] - p[0]), theta, snap_tol)
        dirs.append(np.array([np.cos(ang), np.sin(ang)]))
        mids.append((p + q) / 2.0)

    out = []
    for i in range(n):
        j = (i - 1) % n
        pt = _line_intersection(mids[j], dirs[j], mids[i], dirs[i])
        out.append(approx[i] if pt is None else pt)
    verts = np.array(out, dtype=np.float64)

    # Reject a pathological snap (self-intersection / collapse) by area sanity.
    orig = abs(cv2.contourArea(contour))
    if orig > 0 and not 0.7 <= _poly_area(verts) / orig <= 1.4:
        return None
    return verts


def regularize_silhouette(
    mask: np.ndarray, cfg: PreprocessConfig | None = None
) -> np.ndarray:
    """Return a geometrically-regularised copy of a filled silhouette mask."""
    cfg = cfg or PreprocessConfig()
    if not cfg.regularize_shapes:
        return mask

    binary = (mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return mask

    # Remove a small sheet tilt first, then re-find contours axis-aligned.
    tilt = _global_tilt(contours, cfg.regularize_derotate_max_deg)
    if tilt != 0.0:
        binary = _derotate(binary, tilt)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

    h, w = binary.shape[:2]
    img_area = h * w
    out = np.zeros((h, w), np.uint8)
    drew = False
    for c in contours:
        area = abs(cv2.contourArea(c))
        if area < 1e-3 * img_area:  # ignore specks
            continue
        rect = cv2.minAreaRect(c)
        rw, rh = rect[1]
        rect_area = rw * rh
        score = area / rect_area if rect_area > 0 else 0.0
        if score >= cfg.regularize_rect_score:
            # Collapse to the exact (possibly de-rotated → axis-aligned) rectangle.
            box = cv2.boxPoints(rect).astype(np.int32)
            cv2.fillPoly(out, [box], 255)
            drew = True
            continue
        verts = _regularize_contour(c, cfg)
        if verts is None:
            cv2.drawContours(out, [c], -1, 255, thickness=cv2.FILLED)
        else:
            cv2.fillPoly(out, [np.round(verts).astype(np.int32)], 255)
        drew = True

    return out if drew else mask
