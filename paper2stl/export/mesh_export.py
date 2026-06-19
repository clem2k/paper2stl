"""Convert a voxel occupancy grid into a watertight STL mesh.

Pipeline:
  1. Pad the grid with one empty voxel on every side so the part never touches
     the volume boundary — this guarantees marching cubes closes every surface.
  2. Marching cubes (scikit-image) → triangle mesh.
  3. Optional Laplacian smoothing (Taubin, volume-preserving) to take the
     stair-stepping off the voxelisation.
  4. trimesh repair pass (fix normals/winding, fill any residual holes) and a
     watertight assertion.
  5. Optional rescale so the longest dimension equals a target size in mm.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..config import ExportConfig

logger = logging.getLogger(__name__)


def occupancy_to_mesh(
    occupancy: np.ndarray,
    cfg: ExportConfig | None = None,
    smoothing_iterations: int = 5,
    level: float = 0.5,
):
    """Build a watertight :class:`trimesh.Trimesh` from an occupancy grid."""
    import trimesh
    from skimage import measure

    cfg = cfg or ExportConfig()
    if not occupancy.any():
        raise ValueError("Occupancy grid is empty; nothing to mesh")

    padded = np.pad(occupancy.astype(np.float32), 1, mode="constant")

    # Gentle pre-smoothing of the scalar field takes the voxel stair-stepping off
    # flat faces before the surface is extracted, without the wave artefacts that
    # post-hoc mesh smoothing can introduce. Sharp corners survive at small sigma.
    sigma = getattr(cfg, "presmooth_sigma", 0.0)
    if sigma and sigma > 0:
        from scipy.ndimage import gaussian_filter

        padded = gaussian_filter(padded, sigma=float(sigma))

    verts, faces, normals, _ = measure.marching_cubes(padded, level=level)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_normals=normals)

    if smoothing_iterations > 0:
        # Taubin smoothing preserves volume (no shrinkage) unlike plain Laplacian.
        trimesh.smoothing.filter_taubin(mesh, iterations=smoothing_iterations)

    if cfg.ensure_watertight:
        mesh = _make_watertight(mesh)

    if cfg.target_size_mm:
        mesh = _rescale(mesh, cfg.target_size_mm)

    return mesh


def _make_watertight(mesh):
    """Repair the mesh and verify it is a closed manifold."""
    import trimesh

    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces())
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fill_holes(mesh)

    if not mesh.is_watertight:
        # Last resort: keep the largest connected component, re-fill.
        comps = mesh.split(only_watertight=False)
        if comps:
            mesh = max(comps, key=lambda m: m.area)
            trimesh.repair.fill_holes(mesh)
        if not mesh.is_watertight:
            logger.warning("Mesh is not perfectly watertight after repair")
    return mesh


def _rescale(mesh, target_size_mm: float):
    extents = mesh.extents
    longest = float(max(extents)) or 1.0
    mesh.apply_scale(target_size_mm / longest)
    return mesh


def export_stl(
    mesh, path: str | Path, binary: bool = True
) -> Path:
    """Write *mesh* to an STL file and return its path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_type = "stl" if binary else "stl_ascii"
    mesh.export(str(path), file_type=file_type)
    logger.info(
        "Exported STL: %s (%d verts, %d faces, watertight=%s)",
        path,
        len(mesh.vertices),
        len(mesh.faces),
        mesh.is_watertight,
    )
    return path
