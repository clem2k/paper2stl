"""Tests for the photogrammetry-style cross-view registration."""

import numpy as np

from rhodia.config import PipelineConfig
from rhodia.reconstruction import ViewSilhouette, reconstruct
from rhodia.reconstruction.registration import (
    _best_offset,
    _content_bbox,
    _uniform_scale,
    build_view_planes,
)


def _rect(h, w, top, left, rh, rw):
    """Canvas (h, w) with a filled rectangle of size (rh, rw) at (top, left)."""
    m = np.zeros((h, w), np.uint8)
    m[top : top + rh, left : left + rw] = 255
    return m


def test_uniform_scale_preserves_aspect():
    # A 100x200 box asked to fit a 50x100 grid → single factor 0.5 for both.
    s = _uniform_scale(pw=200, ph=100, target_u=100, target_v=50)
    assert abs(s - 0.5) < 1e-9


def test_content_bbox_ignores_speck():
    # Part is a centred block; a 1px speck sits far away in the corner.
    m = _rect(100, 100, top=30, left=30, rh=40, rw=40)
    m[2, 2] = 255  # stray speck
    r0, r1, c0, c1 = _content_bbox(m)
    # Box must hug the block, not stretch to include the corner speck.
    assert (r0, c0) == (30, 30)
    assert (r1, c1) == (69, 69)


def test_best_offset_locks_onto_reference_peak():
    axis_len = 100
    length = 20
    # Reference profile peaked around index 60.
    reference = np.zeros(axis_len)
    reference[55:75] = 1.0
    profile = np.ones(length)
    off = _best_offset(profile, length, axis_len, reference, tolerance=0.5)
    # Best overlap places the [off, off+20) window over [55, 75).
    assert 53 <= off <= 57


def test_best_offset_centres_without_reference():
    off = _best_offset(np.ones(20), 20, 100, reference=None, tolerance=0.15)
    assert off == (100 - 20) // 2


def test_registration_aligns_shifted_shared_axis():
    """Two views sharing world-X, drawn shifted on their sheets, get realigned.

    'front' and 'top' both observe world-X (columns). We draw the same
    L-weighted silhouette but translated differently on each sheet; after
    registration their X projection profiles should line up (matching centroids).
    """
    # Asymmetric mass: a wide bar with a tall stub on its right end, so the
    # column-profile centroid is not at the bbox centre — centring alone would
    # not align the two; correlation must.
    def lshape(top, left):
        m = np.zeros((200, 200), np.uint8)
        m[top : top + 20, left : left + 80] = 255          # horizontal bar
        m[top - 40 : top + 20, left + 60 : left + 80] = 255  # right stub upward
        return m

    front = ViewSilhouette("front", lshape(top=120, left=30))
    top = ViewSilhouette("top", lshape(top=120, left=110))  # shifted right on sheet

    dims = (64, 48, 50)  # (Nx, Ny, Nz)
    planes = build_view_planes([front, top], dims, PipelineConfig().reconstruction)

    # Both planes are (n_v, n_u) with u = world-X. Column profile = mass per X.
    def x_centroid(plane):
        prof = plane.sum(axis=0).astype(float)
        return float((np.arange(prof.size) * prof).sum() / prof.sum())

    c_front = x_centroid(planes[id(front)])
    c_top = x_centroid(planes[id(top)])
    # Registration should bring the shared-axis centroids within a few voxels.
    assert abs(c_front - c_top) <= 3.0


def test_misaligned_cube_still_reconstructs_box():
    """A cube whose square is shifted/rescaled per sheet still carves a solid."""
    def square(h, w, top, left, side):
        return _rect(h, w, top, left, side, side)

    cfg = PipelineConfig()
    cfg.reconstruction.voxel_resolution = 48
    views = [
        ViewSilhouette("front", square(200, 200, 40, 40, 120)),
        ViewSilhouette("top", square(200, 200, 70, 20, 120)),   # shifted
        ViewSilhouette("right", square(180, 180, 30, 30, 110)),  # different scale
    ]
    occ, _ = reconstruct(views, cfg.reconstruction)
    assert occ.any()
    assert occ.mean() > 0.1


def test_alignment_toggle_runs_both_paths():
    cfg = PipelineConfig()
    cfg.reconstruction.voxel_resolution = 32
    views = [
        ViewSilhouette("front", _rect(200, 200, 40, 40, 120, 120)),
        ViewSilhouette("top", _rect(200, 200, 40, 40, 120, 120)),
        ViewSilhouette("right", _rect(200, 200, 40, 40, 120, 120)),
    ]
    cfg.reconstruction.align_views = True
    occ_on, _ = reconstruct(views, cfg.reconstruction)
    cfg.reconstruction.align_views = False
    occ_off, _ = reconstruct(views, cfg.reconstruction)
    assert occ_on.any() and occ_off.any()
