"""Apply 'detail page' features as local CSG operations on the solid.

A red frame on a main view references a separate scan (the detail page) that
zooms into a region of one face — e.g. an engraving, pocket or boss.  We treat
each detail as a local boolean: the detail's silhouette is projected onto the
target face and either *subtracted* (pocket / engraving) or *added* (boss) over
a shallow depth measured from that face.

Working on the same voxel grid as the main reconstruction keeps everything
watertight after marching cubes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from ..reconstruction.views import VIEW_AXES

logger = logging.getLogger(__name__)


@dataclass
class DetailPage:
    """A detail feature to stamp onto one face of the solid.

    Attributes
    ----------
    target_view : str
        Which face the detail belongs to (key of VIEW_AXES).
    mask : np.ndarray
        Binary silhouette of the feature (255 = feature).
    mode : str
        ``"pocket"`` (subtract) or ``"boss"`` (add).
    depth_frac : float
        Feature depth as a fraction of the solid's extent along the face normal.
    region : tuple[float, float, float, float]
        (cx, cy, w, h) placement of the feature on the face, all in [0, 1]
        normalised face coordinates (u = column, v = row of that view).
    """

    target_view: str
    mask: np.ndarray
    mode: str = "pocket"
    depth_frac: float = 0.15
    region: tuple[float, float, float, float] = (0.5, 0.5, 0.3, 0.3)


def _face_in_plane_mask(detail: DetailPage, dims, u_axis, v_axis) -> np.ndarray:
    """Render the detail feature into a full-face (n_u × n_v) mask."""
    n_u, n_v = dims[u_axis], dims[v_axis]
    cx, cy, w, h = detail.region
    fw, fh = max(1, int(w * n_u)), max(1, int(h * n_v))
    feat = cv2.resize(detail.mask, (fw, fh), interpolation=cv2.INTER_NEAREST) > 0

    face = np.zeros((n_v, n_u), dtype=bool)  # (rows=v, cols=u)
    x0 = int(cx * n_u - fw / 2)
    y0 = int(cy * n_v - fh / 2)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(n_u, x0 + fw), min(n_v, y0 + fh)
    face[y0:y1, x0:x1] = feat[: y1 - y0, : x1 - x0]
    return face  # indexed [v, u]


def apply_detail_pages(
    occupancy: np.ndarray, details: list[DetailPage]
) -> np.ndarray:
    """Return a new occupancy grid with all detail features applied."""
    occ = occupancy.copy()
    for detail in details:
        if detail.target_view not in VIEW_AXES:
            logger.warning("Unknown detail target view '%s'; skipped", detail.target_view)
            continue
        u_axis, u_flip, v_axis, v_flip, w_axis = VIEW_AXES[detail.target_view]
        face = _face_in_plane_mask(detail, occ.shape, u_axis, v_axis)
        if u_flip:
            face = face[:, ::-1]
        if v_flip:
            face = face[::-1, :]

        n_w = occ.shape[w_axis]
        depth = max(1, int(detail.depth_frac * n_w))
        # 'front'-type faces have their surface at the high end of the normal
        # axis; we measure inward from whichever end the view looks at.
        near_high = detail.target_view in ("front", "top", "right")
        w_slice = (
            slice(n_w - depth, n_w) if near_high else slice(0, depth)
        )

        # Broadcast the face mask across the depth slab.
        feat_vol = np.broadcast_to(face[:, :, None], (face.shape[0], face.shape[1], depth))
        local_axes = [v_axis, u_axis, w_axis]
        order = [local_axes.index(0), local_axes.index(1), local_axes.index(2)]
        feat_vol = np.transpose(feat_vol, order)

        idx = [slice(None)] * 3
        idx[w_axis] = w_slice
        idx = tuple(idx)

        if detail.mode == "boss":
            occ[idx] |= feat_vol
        else:  # pocket / engraving (default)
            occ[idx] &= ~feat_vol
        logger.info("Applied %s detail on '%s' face", detail.mode, detail.target_view)
    return occ
