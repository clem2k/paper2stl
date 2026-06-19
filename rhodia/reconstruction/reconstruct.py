"""Top-level reconstruction: silhouettes → voxel occupancy grid."""

from __future__ import annotations

import logging

import numpy as np

from ..config import ReconstructionConfig
from .align import BoundingBox, register_views
from .csg_recon import carve_visual_hull
from .infer_missing import complete_missing_views, unconstrained_axes
from .views import ViewSilhouette

logger = logging.getLogger(__name__)


def _bound_extrusion(
    occupancy: np.ndarray, axis: int, frac: float
) -> np.ndarray:
    """Limit a fully-unconstrained extruded axis to a finite default depth.

    Without any silhouette along ``axis`` the visual hull is an infinite prism
    (the whole grid along that axis).  We centre a slab of thickness
    ``frac * N`` so a lone view becomes a sensible plate instead of filling the
    bounding box.
    """
    n = occupancy.shape[axis]
    thickness = max(1, int(round(frac * n)))
    start = (n - thickness) // 2
    keep = np.zeros(n, dtype=bool)
    keep[start : start + thickness] = True
    shape = [1, 1, 1]
    shape[axis] = n
    return occupancy & keep.reshape(shape)


def reconstruct(
    views: list[ViewSilhouette], cfg: ReconstructionConfig | None = None
) -> tuple[np.ndarray, BoundingBox]:
    """Run alignment, missing-view completion and visual-hull carving.

    Returns the boolean occupancy grid and its :class:`BoundingBox`.
    """
    cfg = cfg or ReconstructionConfig()
    if not views:
        raise ValueError("reconstruct() needs at least one view")

    logger.info("Reconstructing from views: %s", [v.name for v in views])

    completed = complete_missing_views(views, cfg)
    bbox = register_views(completed, resolution=cfg.voxel_resolution)
    logger.info("Registered %s", bbox)

    occupancy = carve_visual_hull(completed, bbox, cfg)

    # Bound any axis still observed by nobody (pure extrusion) to a finite slab.
    for axis in unconstrained_axes(completed):
        occupancy = _bound_extrusion(occupancy, axis, cfg.default_extrude_frac)
        logger.info("Bounded unconstrained axis %d to default depth", axis)

    if cfg.use_neural_completion:
        from .neural_recon import neural_complete

        occupancy = neural_complete(
            occupancy, completed, weights=cfg.neural_weights
        )

    logger.info("Reconstruction done: %d solid voxels", int(occupancy.sum()))
    return occupancy, bbox
