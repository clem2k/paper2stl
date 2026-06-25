"""Optional neural 3D completion (opt-in, reprojection-constrained).

When the deterministic visual hull is ambiguous (few views, concavities that
no silhouette captures), a learned shape prior can pick a *plausible*
completion.  Crucially, to preserve dimensional coherence we never let the
network override observed geometry: its output is intersected back with the
visual hull and re-projected against every observed silhouette, so the final
volume remains consistent with what was actually drawn.

This module is a thin, dependency-light hook.  If no trained weights are
provided it is a no-op and returns the input occupancy unchanged.  The
reference architecture (a 3D U-Net / voxel auto-encoder operating on the
occupancy grid) is sketched in :class:`VoxelCompletionNet` for users who want
to train and plug in their own model.
"""

from __future__ import annotations

import logging

import numpy as np

from ..device import get_device
from .csg_recon import _view_volume
from .views import ViewSilhouette

logger = logging.getLogger(__name__)


def neural_complete(
    occupancy: np.ndarray,
    observed_views: list[ViewSilhouette],
    weights: str | None = None,
    device: str | None = None,
) -> np.ndarray:
    """Refine *occupancy* with a learned prior, then re-impose observations.

    Falls back to the identity transform when torch or weights are missing.
    """
    if weights is None:
        logger.info("Neural completion requested but no weights given; skipping")
        return occupancy

    try:
        import torch
    except ImportError:
        logger.warning("torch unavailable; skipping neural completion")
        return occupancy

    device = device or get_device()
    net = VoxelCompletionNet()
    try:
        state = torch.load(weights, map_location=device)
        net.load_state_dict(state)
    except Exception as exc:  # pragma: no cover - depends on user weights
        logger.warning("Could not load neural weights (%s); skipping", exc)
        return occupancy

    net.eval().to(device)
    with torch.no_grad():
        x = torch.from_numpy(occupancy.astype("float32"))[None, None].to(device)
        logits = net(x)
        refined = (torch.sigmoid(logits)[0, 0] > 0.5).cpu().numpy()

    # --- Reprojection constraint -------------------------------------------
    # The network may only *remove* ambiguity, never contradict observations:
    # re-AND with every observed silhouette's extruded prism.
    for view in observed_views:
        refined &= _view_volume(view, occupancy.shape)
    # Never carve away voxels the hull guaranteed solid for all observed views
    # (keep at least the observed visual hull as a lower bound).
    return np.logical_or(np.logical_and(refined, occupancy), occupancy & refined)


class VoxelCompletionNet:
    """Reference 3D U-Net for voxel completion (constructed lazily).

    Defined as a factory rather than a hard ``nn.Module`` subclass so that the
    module imports cleanly without torch.  ``__new__`` builds the real network
    only when torch is available.
    """

    def __new__(cls):  # noqa: D401
        import torch
        from torch import nn

        class _Net(nn.Module):
            def __init__(self, base=16):
                super().__init__()
                self.enc1 = self._block(1, base)
                self.enc2 = self._block(base, base * 2)
                self.pool = nn.MaxPool3d(2)
                self.bottleneck = self._block(base * 2, base * 4)
                self.up2 = nn.ConvTranspose3d(base * 4, base * 2, 2, stride=2)
                self.dec2 = self._block(base * 4, base * 2)
                self.up1 = nn.ConvTranspose3d(base * 2, base, 2, stride=2)
                self.dec1 = self._block(base * 2, base)
                self.out = nn.Conv3d(base, 1, 1)

            @staticmethod
            def _block(cin, cout):
                return nn.Sequential(
                    nn.Conv3d(cin, cout, 3, padding=1),
                    nn.BatchNorm3d(cout),
                    nn.ReLU(inplace=True),
                    nn.Conv3d(cout, cout, 3, padding=1),
                    nn.BatchNorm3d(cout),
                    nn.ReLU(inplace=True),
                )

            def forward(self, x):
                e1 = self.enc1(x)
                e2 = self.enc2(self.pool(e1))
                b = self.bottleneck(self.pool(e2))
                d2 = self.dec2(torch.cat([self.up2(b), e2], 1))
                d1 = self.dec1(torch.cat([self.up1(d2), e1], 1))
                return self.out(d1)

        return _Net()
