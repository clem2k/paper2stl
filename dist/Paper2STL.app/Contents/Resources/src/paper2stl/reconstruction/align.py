"""Register independent 2D views into one consistent 3D bounding box.

Every scan is drawn at its own scale, so before carving we must reconcile the
*shared dimensions*: e.g. ``top`` and ``front`` both observe world-X (width),
``front`` and ``right`` both observe world-Z (height).  We collect every
per-axis extent estimate (in normalised units), reconcile duplicates, and
derive an integer voxel grid whose aspect ratio matches the real part.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .views import AXIS_NAME, ViewSilhouette


@dataclass
class BoundingBox:
    """Consistent voxel grid description."""

    dims: tuple[int, int, int]        # (Nx, Ny, Nz) in voxels
    extent: tuple[float, float, float]  # relative physical extent per axis

    def __str__(self) -> str:
        d = ", ".join(f"{AXIS_NAME[i]}={self.dims[i]}" for i in range(3))
        return f"BoundingBox({d})"


def _tight_extent(mask: np.ndarray) -> tuple[int, int]:
    """Width/height of the silhouette's tight bounding box (px)."""
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return mask.shape[1], mask.shape[0]
    return int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def register_views(
    views: list[ViewSilhouette], resolution: int = 128
) -> BoundingBox:
    """Reconcile shared axes and return an integer voxel :class:`BoundingBox`.

    The relative extent of each world axis is estimated by averaging every
    view that observes it (after normalising each view's longest side to 1).
    """
    # axis -> list of normalised extent estimates
    estimates: dict[int, list[float]] = {0: [], 1: [], 2: []}
    for v in views:
        w, h = _tight_extent(v.mask)
        longest = max(w, h) or 1
        u_axis, _, v_axis, _, _ = v.axes
        estimates[u_axis].append(w / longest)
        estimates[v_axis].append(h / longest)

    extent = []
    for axis in (0, 1, 2):
        vals = estimates[axis]
        # Unobserved axis → assume a moderate default depth (handled later by
        # the missing-view completion); keep it from collapsing to zero.
        extent.append(float(np.mean(vals)) if vals else 0.6)

    scale = resolution / max(extent)
    dims = tuple(max(8, int(round(e * scale))) for e in extent)
    return BoundingBox(dims=dims, extent=tuple(extent))
