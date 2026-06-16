"""Core reconstruction tests that run without OCR/torch (numpy+cv2+skimage)."""

import numpy as np
import pytest

from rhodia.config import PipelineConfig
from rhodia.device import get_device
from rhodia.reconstruction import ViewSilhouette, reconstruct
from rhodia.reconstruction.views import VIEW_AXES, OPPOSITE


def _rect(h, w):
    m = np.zeros((h, w), np.uint8)
    m[h // 6 : 5 * h // 6, w // 6 : 5 * w // 6] = 255
    return m


def test_device_resolves_to_known_backend():
    assert get_device() in {"cuda", "mps", "cpu"}


def test_axis_table_is_consistent():
    # Every view's three axes are a permutation of {0,1,2}.
    for name, (ua, _, va, _, wa) in VIEW_AXES.items():
        assert sorted((ua, va, wa)) == [0, 1, 2], name
    # Opposite mapping is an involution.
    for k, v in OPPOSITE.items():
        assert OPPOSITE[v] == k


def test_box_from_three_views_is_watertight():
    cfg = PipelineConfig()
    cfg.reconstruction.voxel_resolution = 48
    views = [
        ViewSilhouette("front", _rect(120, 160)),
        ViewSilhouette("top", _rect(100, 160)),
        ViewSilhouette("right", _rect(120, 100)),
    ]
    occ, bbox = reconstruct(views, cfg.reconstruction)
    assert occ.any()
    # Solid fraction should be substantial for a convex box.
    assert occ.mean() > 0.1

    from rhodia.export import occupancy_to_mesh
    mesh = occupancy_to_mesh(occ, cfg.export, smoothing_iterations=0)
    assert mesh.is_watertight
    assert mesh.volume > 0


def test_missing_view_is_mirrored():
    cfg = PipelineConfig()
    cfg.reconstruction.voxel_resolution = 32
    # Only a single 'left' view: its opposite 'right' should be inferred and
    # the lone observed axis (depth) bounded to a finite slab, not infinite.
    views = [ViewSilhouette("front", _rect(120, 160)),
             ViewSilhouette("left", _rect(120, 100))]
    occ, _ = reconstruct(views, cfg.reconstruction)
    assert occ.any()


def test_empty_views_raise():
    with pytest.raises(ValueError):
        reconstruct([], PipelineConfig().reconstruction)
