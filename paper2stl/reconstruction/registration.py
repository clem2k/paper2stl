"""Photogrammetry-style cross-view registration of orthographic silhouettes.

Each scan places its drawing arbitrarily on the page: the same world axis is
observed by several views (e.g. ``front`` and ``top`` both see world-X = width),
yet the part may be drawn slightly shifted — or at a slightly different scale —
from one sheet to the next.  Simply cropping every silhouette to its bounding
box and stretching it to fill the grid (the legacy behaviour) aligns only the
bounding-box corners and, worse, distorts proportions when the two in-plane
extents are stretched independently.

Here we register the views the way a photogrammetry pipeline would:

1. **Uniform-scale consensus** — each view is scaled by a single (isotropic)
   factor so its two in-plane extents best match the consensus grid extent of
   the axes it observes.  Proportions are preserved; sheets drawn at different
   sizes are reconciled.
2. **Profile cross-correlation** — for every world axis the 1-D projection
   profile of each view is slid (within a tolerance window) to maximise its
   overlap with the running consensus profile of the views already placed.
   This recovers the per-sheet translation offset feature-by-feature, not just
   by bounding-box corners.

The result, per view, is a boolean in-plane occupancy plane already positioned
in the world grid, ready to be extruded by the visual-hull carver.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from ..config import ReconstructionConfig
from .views import ViewSilhouette

logger = logging.getLogger(__name__)


def _content_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Tight bounding box ``(r0, r1, c0, c1)`` of the part, or None if empty.

    The box is taken around the *largest connected component* rather than the
    raw foreground, so a stray speck or a faint leftover mark far from the part
    cannot inflate the box and throw off scale/registration.
    """
    binary = (mask > 0).astype(np.uint8)
    if not binary.any():
        return None
    n, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n <= 2:  # background + a single component → plain bounding box
        ys, xs = np.where(binary)
        return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    # 0 is background; pick the largest remaining component as the part.
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x = int(stats[largest, cv2.CC_STAT_LEFT])
    y = int(stats[largest, cv2.CC_STAT_TOP])
    w = int(stats[largest, cv2.CC_STAT_WIDTH])
    h = int(stats[largest, cv2.CC_STAT_HEIGHT])
    return y, y + h - 1, x, x + w - 1


def _resize_mask(crop: np.ndarray, vw: int, vh: int) -> np.ndarray:
    """Resize a binary mask with area-averaging + 0.5 threshold.

    Area interpolation antialiases the edge so a downscaled diagonal becomes a
    smooth ramp rather than the hard stair-steps ``INTER_NEAREST`` would leave;
    thresholding at the half-coverage level keeps it a clean boolean plane.
    """
    interp = cv2.INTER_AREA if (vw < crop.shape[1] or vh < crop.shape[0]) else cv2.INTER_LINEAR
    resized = cv2.resize(crop.astype(np.uint8), (vw, vh), interpolation=interp)
    return resized >= 128


def _uniform_scale(pw: int, ph: int, target_u: int, target_v: int) -> float:
    """Single isotropic factor best matching (pw→target_u, ph→target_v).

    Least-squares solution of ``min_s (s*pw - target_u)^2 + (s*ph - target_v)^2``
    so the drawing's aspect ratio is preserved (no independent-axis stretch).
    """
    denom = pw * pw + ph * ph
    if denom == 0:
        return 1.0
    return (target_u * pw + target_v * ph) / denom


def _best_offset(
    profile: np.ndarray,
    length: int,
    axis_len: int,
    reference: np.ndarray | None,
    tolerance: float,
) -> int:
    """Offset (top/left) at which to drop a length-``length`` profile.

    Centres the profile when there is no reference yet; otherwise searches a
    ``±tolerance*axis_len`` window around centre for the shift maximising the
    cross-correlation (overlap) with the accumulated *reference* profile.
    """
    free = axis_len - length
    if free <= 0:
        return 0
    centre = free // 2
    if reference is None or not reference.any() or tolerance <= 0:
        return centre

    max_shift = max(1, int(round(tolerance * axis_len)))
    lo = max(0, centre - max_shift)
    hi = min(free, centre + max_shift)

    best_off, best_score = centre, -1.0
    for off in range(lo, hi + 1):
        score = float(np.dot(reference[off : off + length], profile))
        # Prefer the score-maximising offset; break ties toward the centre.
        if score > best_score or (
            score == best_score and abs(off - centre) < abs(best_off - centre)
        ):
            best_score, best_off = score, off
    return best_off


def _place_plane(
    view: ViewSilhouette,
    dims: tuple[int, int, int],
    refs: dict[int, np.ndarray],
    tolerance: float,
) -> np.ndarray:
    """Scale, orient and position one view into a ``(n_v, n_u)`` boolean plane."""
    u_axis, u_flip, v_axis, v_flip, _ = view.axes
    n_u, n_v = dims[u_axis], dims[v_axis]

    box = _content_bbox(view.mask)
    if box is None:
        return np.zeros((n_v, n_u), dtype=bool)
    r0, r1, c0, c1 = box
    crop = view.mask[r0 : r1 + 1, c0 : c1 + 1]
    ph, pw = crop.shape[:2]

    # Uniform scale → preserve proportions while matching the grid extents.
    scale = _uniform_scale(pw, ph, n_u, n_v)
    vw = int(np.clip(round(scale * pw), 1, n_u))
    vh = int(np.clip(round(scale * ph), 1, n_v))
    small = _resize_mask(crop, vw, vh)

    if u_flip:
        small = small[:, ::-1]
    if v_flip:
        small = small[::-1, :]

    # 1-D projection profiles (mass per column / row) along each in-plane axis.
    prof_u = small.sum(axis=0).astype(np.float64)  # length vw, along world u_axis
    prof_v = small.sum(axis=1).astype(np.float64)  # length vh, along world v_axis
    off_u = _best_offset(prof_u, vw, n_u, refs.get(u_axis), tolerance)
    off_v = _best_offset(prof_v, vh, n_v, refs.get(v_axis), tolerance)

    plane = np.zeros((n_v, n_u), dtype=bool)
    plane[off_v : off_v + vh, off_u : off_u + vw] = small

    # Fold this view's placed profiles into the per-axis consensus references.
    _accumulate(refs, u_axis, n_u, off_u, prof_u)
    _accumulate(refs, v_axis, n_v, off_v, prof_v)
    return plane


def _accumulate(
    refs: dict[int, np.ndarray], axis: int, axis_len: int, off: int, profile: np.ndarray
) -> None:
    """Add a placed profile into the running reference for *axis*."""
    full = refs.get(axis)
    if full is None:
        full = np.zeros(axis_len, dtype=np.float64)
        refs[axis] = full
    full[off : off + profile.shape[0]] += profile


def build_view_planes(
    views: list[ViewSilhouette],
    dims: tuple[int, int, int],
    cfg: ReconstructionConfig | None = None,
) -> dict[int, np.ndarray]:
    """Return ``id(view) -> (n_v, n_u)`` boolean planes, registered across views.

    Views are processed highest-confidence first so the most trustworthy
    silhouettes anchor the per-axis consensus that the rest align against.
    """
    cfg = cfg or ReconstructionConfig()
    refs: dict[int, np.ndarray] = {}
    planes: dict[int, np.ndarray] = {}
    for view in sorted(views, key=lambda v: v.confidence, reverse=True):
        planes[id(view)] = _place_plane(view, dims, refs, cfg.align_tolerance)
        logger.debug(
            "Registered view '%s' (conf=%.2f) into grid plane", view.name, view.confidence
        )
    return planes
