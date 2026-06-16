"""Stage C — 3D reconstruction from orthographic silhouettes."""

from .views import ViewSilhouette, VIEW_AXES, OPPOSITE
from .align import register_views, BoundingBox
from .csg_recon import carve_visual_hull
from .infer_missing import complete_missing_views
from .reconstruct import reconstruct

__all__ = [
    "ViewSilhouette",
    "VIEW_AXES",
    "OPPOSITE",
    "register_views",
    "BoundingBox",
    "carve_visual_hull",
    "complete_missing_views",
    "reconstruct",
]
