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

from .align import BoundingBox
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


def _view_volume(view: ViewSilhouette, dims: tuple[int, int, int]) -> np.ndarray:
    """Boolean occupancy (Nx,Ny,Nz) for one extruded silhouette."""
    u_axis, u_flip, v_axis, v_flip, w_axis = view.axes
    n_u, n_v, n_w = dims[u_axis], dims[v_axis], dims[w_axis]

    # Register by cropping to content, then resize to the grid resolution of
    # the two in-plane axes. cv2.resize takes (width=cols=u, height=rows=v).
    cropped = _crop_to_content(view.mask)
    mask = cv2.resize(cropped, (n_u, n_v), interpolation=cv2.INTER_NEAREST)
    mask = (mask > 0)

    if u_flip:
        mask = mask[:, ::-1]
    if v_flip:
        mask = mask[::-1, :]

    # mask has local axes (v, u). Extrude along w → (v, u, w).
    vol_local = np.broadcast_to(mask[:, :, None], (n_v, n_u, n_w))

    # Reorder local axes (v_axis, u_axis, w_axis) → world (X, Y, Z).
    local_axes = [v_axis, u_axis, w_axis]
    order = [local_axes.index(0), local_axes.index(1), local_axes.index(2)]
    return np.ascontiguousarray(np.transpose(vol_local, order))


def carve_visual_hull(
    views: list[ViewSilhouette], bbox: BoundingBox
) -> np.ndarray:
    """Intersect all extruded silhouettes into an occupancy grid.

    Returns
    -------
    np.ndarray
        Boolean array of shape ``bbox.dims`` (True = solid).
    """
    if not views:
        raise ValueError("Cannot reconstruct: no views provided")

    occupancy = np.ones(bbox.dims, dtype=bool)
    for view in views:
        vol = _view_volume(view, bbox.dims)
        occupancy &= vol
        logger.debug(
            "Carved view '%s' → %d solid voxels remaining",
            view.name,
            int(occupancy.sum()),
        )

    if not occupancy.any():
        logger.warning("Visual hull is empty after carving; views may be inconsistent")
    return occupancy
