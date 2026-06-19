"""Turn a binary stroke image into clean straight vector segments.

Hand-drawn lines are wobbly and fragmented.  We:
  1. Detect candidate segments with the probabilistic Hough transform.
  2. Cluster collinear/co-oriented segments (greedy, angle+distance gated).
  3. Refit each cluster with total-least-squares (robust to the wobble) to
     emit one strictly-straight segment per real edge.

The optional deep route (a thin wireframe-parsing network) is intentionally
left as a pluggable hook — the classical route above is fully functional and
deterministic, and is what the rest of the pipeline consumes.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import PreprocessConfig
from ..utils.geometry import Segment, angular_distance


def _hough_segments(binary: np.ndarray, cfg: PreprocessConfig) -> list[Segment]:
    lines = cv2.HoughLinesP(
        binary,
        rho=1,
        theta=np.pi / 180,
        threshold=cfg.hough_threshold,
        minLineLength=cfg.hough_min_line_length,
        maxLineGap=cfg.hough_max_line_gap,
    )
    if lines is None:
        return []
    return [Segment(*map(float, ln[0])) for ln in lines]


def _project_endpoints(cluster: list[Segment], pct: float = 100.0) -> Segment:
    """Refit a cluster into one segment, with optional partial straightening.

    pct=100 → full TLS refit (perfectly straight, default behaviour).
    pct=0   → raw Hough endpoints unchanged (preserves curves / wobble).
    Intermediate values blend linearly between the two.
    """
    pts = np.vstack([[s.x1, s.y1] for s in cluster] + [[s.x2, s.y2] for s in cluster])
    centroid = pts.mean(axis=0)
    # Principal direction via SVD (robust TLS line fit).
    _, _, vt = np.linalg.svd(pts - centroid)
    direction = vt[0]
    t = (pts - centroid) @ direction
    i_min, i_max = int(t.argmin()), int(t.argmax())
    tls_min = centroid + direction * t[i_min]
    tls_max = centroid + direction * t[i_max]
    if pct >= 100.0:
        return Segment(tls_min[0], tls_min[1], tls_max[0], tls_max[1])
    alpha = max(0.0, min(1.0, pct / 100.0))
    raw_min = pts[i_min]
    raw_max = pts[i_max]
    p_min = (1 - alpha) * raw_min + alpha * tls_min
    p_max = (1 - alpha) * raw_max + alpha * tls_max
    return Segment(p_min[0], p_min[1], p_max[0], p_max[1])


def _merge_segments(segs: list[Segment], cfg: PreprocessConfig) -> list[Segment]:
    """Greedily merge co-linear, co-oriented, nearby segments."""
    used = [False] * len(segs)
    merged: list[Segment] = []
    ang_tol = np.deg2rad(cfg.line_merge_angle_deg)

    for i, s in enumerate(segs):
        if used[i]:
            continue
        cluster = [s]
        used[i] = True
        ref_ang = s.angle
        cx, cy = s.midpoint
        for j in range(i + 1, len(segs)):
            if used[j]:
                continue
            t = segs[j]
            if angular_distance(ref_ang, t.angle) > ang_tol:
                continue
            # Perpendicular offset between the two (near-parallel) lines.
            dx, dy = np.cos(ref_ang), np.sin(ref_ang)
            mx, my = t.midpoint
            perp = abs(-dy * (mx - cx) + dx * (my - cy))
            if perp <= cfg.line_merge_dist_px:
                cluster.append(t)
                used[j] = True
        merged.append(_project_endpoints(cluster, cfg.line_straighten_pct))
    return merged


def vectorize_lines(
    binary: np.ndarray, cfg: PreprocessConfig | None = None
) -> list[Segment]:
    """Return a list of straight :class:`Segment` objects from a binary image."""
    cfg = cfg or PreprocessConfig()
    raw = _hough_segments(binary, cfg)
    if not raw:
        return []
    return _merge_segments(raw, cfg)


def rasterize_silhouette(
    segments: list[Segment], shape: tuple[int, int], thickness: int = 2
) -> np.ndarray:
    """Render segments into a binary image and fill enclosed regions.

    The reconstruction stage needs a *filled silhouette* per view (the region
    occupied by the part as seen from that direction), not just its outline.
    We draw the straightened wireframe, close it, then flood-fill the exterior
    to recover the interior as foreground.
    """
    canvas = np.zeros(shape, dtype=np.uint8)
    for s in segments:
        # LINE_8 (no anti-aliasing) keeps the silhouette strictly binary, so the
        # flood-fill and the downstream regularisation see crisp edges rather
        # than feathered grey pixels.
        cv2.line(
            canvas,
            (int(round(s.x1)), int(round(s.y1))),
            (int(round(s.x2)), int(round(s.y2))),
            255,
            thickness,
            cv2.LINE_8,
        )
    canvas = cv2.morphologyEx(canvas, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    # Flood fill from a border seed → exterior; invert to get the interior.
    h, w = shape
    ff = canvas.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 255)
    interior = cv2.bitwise_not(ff)
    return cv2.bitwise_or(canvas, interior)
