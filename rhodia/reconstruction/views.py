"""Orthographic view model and the image→3D axis convention.

World axes (right-handed):
    X = width   (object left → right)
    Y = depth   (object front → back)
    Z = height  (object bottom → top)

Each orthographic view sees the two axes in its plane; the third axis is the
*view (extrusion) axis*.  For every view we record how the silhouette image's
column ``u`` (left→right) and row ``v`` (top→bottom) map onto world axes,
including whether the axis must be flipped (because image rows grow downward,
and opposite views mirror one in-plane axis).

Each entry: ``(u_axis, u_flip, v_axis, v_flip, view_axis)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

X, Y, Z = 0, 1, 2

VIEW_AXES: dict[str, tuple[int, bool, int, bool, int]] = {
    #          u_axis u_flip  v_axis v_flip  view_axis
    "front":  (X,    False,  Z,     True,   Y),
    "rear":   (X,    True,   Z,     True,   Y),
    "top":    (X,    False,  Y,     False,  Z),
    "bottom": (X,    False,  Y,     True,   Z),
    "right":  (Y,    False,  Z,     True,   X),
    "left":   (Y,    True,   Z,     True,   X),
}

OPPOSITE: dict[str, str] = {
    "front": "rear",
    "rear": "front",
    "top": "bottom",
    "bottom": "top",
    "left": "right",
    "right": "left",
}

AXIS_NAME = {X: "X", Y: "Y", Z: "Z"}


@dataclass
class ViewSilhouette:
    """A filled binary silhouette for one orthographic view.

    Attributes
    ----------
    name : str
        Canonical view name (a key of :data:`VIEW_AXES`).
    mask : np.ndarray
        Binary image (uint8, 255 = part, 0 = background), origin top-left.
    confidence : float
        Classification confidence from OCR (used to break ties).
    """

    name: str
    mask: np.ndarray
    confidence: float = 1.0

    @property
    def axes(self) -> tuple[int, bool, int, bool, int]:
        return VIEW_AXES[self.name]

    def in_plane_extents(self) -> dict[int, int]:
        """Pixel extent contributed to each in-plane world axis."""
        u_axis, _, v_axis, _, _ = self.axes
        h, w = self.mask.shape[:2]
        return {u_axis: w, v_axis: h}


def mirror_for_opposite(mask: np.ndarray, src_view: str) -> np.ndarray:
    """Mirror a silhouette so it can stand in for the opposite view.

    Opposite views share both in-plane axes but one is mirrored.  We flip the
    image column (u) to swap chirality; the result is a valid silhouette for
    ``OPPOSITE[src_view]`` because a part's far side has the same outline as
    its near side, left-right reversed.
    """
    return np.ascontiguousarray(mask[:, ::-1])
