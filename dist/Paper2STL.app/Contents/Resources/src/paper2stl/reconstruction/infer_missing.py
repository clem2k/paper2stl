"""Infer/complete missing orthographic views before carving.

Cascade of priors, weakest constraint last:

1. **Opposite-view symmetry** — if a view's opposite is present, mirror it to
   stand in.  This is exact for symmetric parts and a strong prior otherwise.
2. **Unconstrained axis pass-through** — an axis observed by *no* view is left
   unconstrained (the silhouette for that direction is "all solid"), so the
   visual hull simply extrudes the observed cross-section.  Optionally the
   extrusion can be bounded to a default depth to avoid an infinite prism.

The optional neural completion (see :mod:`neural_recon`) is a separate, opt-in
refinement applied *after* carving so it can never violate observed silhouettes.
"""

from __future__ import annotations

import logging

import numpy as np

from ..config import ReconstructionConfig
from .views import OPPOSITE, VIEW_AXES, ViewSilhouette, mirror_for_opposite

logger = logging.getLogger(__name__)

# Which views observe each world axis as an in-plane (not extrusion) axis.
_AXIS_OBSERVERS: dict[int, list[str]] = {0: [], 1: [], 2: []}
for _name, (_ua, _, _va, _, _wa) in VIEW_AXES.items():
    _AXIS_OBSERVERS[_ua].append(_name)
    _AXIS_OBSERVERS[_va].append(_name)


def complete_missing_views(
    views: list[ViewSilhouette], cfg: ReconstructionConfig | None = None
) -> list[ViewSilhouette]:
    """Augment *views* with mirrored opposites where possible.

    Returns a new list; inputs are not mutated.  Pass-through for fully
    unconstrained axes is handled implicitly by :func:`carve_visual_hull`
    (an axis with no silhouette imposes no constraint).
    """
    cfg = cfg or ReconstructionConfig()
    if not cfg.fill_missing:
        return list(views)

    present = {v.name: v for v in views}
    completed = dict(present)

    for name, view in present.items():
        opp = OPPOSITE[name]
        if opp not in completed:
            completed[opp] = ViewSilhouette(
                name=opp,
                mask=mirror_for_opposite(view.mask, name),
                confidence=view.confidence * 0.5,  # inferred, lower trust
            )
            logger.info("Inferred missing view '%s' by mirroring '%s'", opp, name)

    # Report any world axis with no observer at all (pure extrusion).
    observed_axes = set()
    for v in completed.values():
        ua, _, va, _, _ = v.axes
        observed_axes.update({ua, va})
    for axis in (0, 1, 2):
        if axis not in observed_axes:
            logger.warning(
                "World axis %d unconstrained by any view; it will be extruded "
                "(default depth handled by reconstruct()).",
                axis,
            )
    return list(completed.values())


def unconstrained_axes(views: list[ViewSilhouette]) -> list[int]:
    """World axes not observed (in-plane) by any provided view."""
    observed = set()
    for v in views:
        ua, _, va, _, _ = v.axes
        observed.update({ua, va})
    return [a for a in (0, 1, 2) if a not in observed]
