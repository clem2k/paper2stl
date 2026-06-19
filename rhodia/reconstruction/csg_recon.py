"""Voxel visual hull: extrude every silhouette and intersect (CSG AND).

This is the deterministic, dimensionally-exact core of the reconstruction.
Working in a voxel grid (rather than with mesh booleans) guarantees that the
result is a closed manifold once meshed with marching cubes, and makes the
intersection trivially robust.

For each view the silhouette is an infinite prism along its view axis; the
occupied region of the part is the intersection of all such prisms — the
classical *visual hull*.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from ..config import ReconstructionConfig
from .align import BoundingBox
from .registration import build_view_planes
from .views import ViewSilhouette

logger = logging.getLogger(__name__)


def _crop_to_content(mask: np.ndarray) -> np.ndarray:
    """Crop a silhouette to its tight bounding box.

    Each scan places the drawing arbitrarily on the page; cropping to content
    is what actually *registers* the views — afterwards every silhouette spans
    the full extent of its two in-plane axes, so shared axes line up and the
    visual-hull intersection is non-empty.
    """
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return mask
    return mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def _legacy_plane(view: ViewSilhouette, dims: tuple[int, int, int]) -> np.ndarray:
    """Crop-to-content then stretch-to-fill placement (no cross-view registration)."""
    u_axis, u_flip, v_axis, v_flip, _ = view.axes
    n_u, n_v = dims[u_axis], dims[v_axis]
    cropped = _crop_to_content(view.mask)
    mask = cv2.resize(cropped, (n_u, n_v), interpolation=cv2.INTER_NEAREST) > 0
    if u_flip:
        mask = mask[:, ::-1]
    if v_flip:
        mask = mask[::-1, :]
    return mask


def _extrude_plane(
    plane: np.ndarray, view: ViewSilhouette, dims: tuple[int, int, int]
) -> np.ndarray:
    """Extrude a placed ``(n_v, n_u)`` plane along the view axis → world (X,Y,Z)."""
    u_axis, _, v_axis, _, w_axis = view.axes
    n_w = dims[w_axis]

    # plane has local axes (v, u). Extrude along w → (v, u, w).
    vol_local = np.broadcast_to(plane[:, :, None], (*plane.shape, n_w))

    # Reorder local axes (v_axis, u_axis, w_axis) → world (X, Y, Z).
    local_axes = [v_axis, u_axis, w_axis]
    order = [local_axes.index(0), local_axes.index(1), local_axes.index(2)]
    return np.ascontiguousarray(np.transpose(vol_local, order))


def carve_visual_hull(
    views: list[ViewSilhouette],
    bbox: BoundingBox,
    cfg: ReconstructionConfig | None = None,
) -> np.ndarray:
    """Intersect all extruded silhouettes into an occupancy grid.

    When ``cfg.align_views`` is set (default), silhouettes are registered across
    views by :func:`registration.build_view_planes` (uniform-scale consensus +
    profile cross-correlation) so drawings placed differently on each sheet are
    realigned.  Otherwise the legacy crop-and-stretch placement is used.

    Returns
    -------
    np.ndarray
        Boolean array of shape ``bbox.dims`` (True = solid).
    """
    if not views:
        raise ValueError("Cannot reconstruct: no views provided")
    cfg = cfg or ReconstructionConfig()

    if cfg.align_views:
        planes = build_view_planes(views, bbox.dims, cfg)
    else:
        planes = {id(v): _legacy_plane(v, bbox.dims) for v in views}

    occupancy = np.ones(bbox.dims, dtype=bool)
    for view in views:
        vol = _extrude_plane(planes[id(view)], view, bbox.dims)
        occupancy &= vol
        logger.debug(
            "Carved view '%s' → %d solid voxels remaining",
            view.name,
            int(occupancy.sum()),
        )

    if not occupancy.any():
        logger.warning("Visual hull is empty after carving; views may be inconsistent")
    return occupancy
