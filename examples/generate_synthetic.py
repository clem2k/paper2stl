"""Generate synthetic Rhodia-style scans for a runnable end-to-end demo.

Produces, for a chosen primitive (an L-bracket by default), a set of scan
images that look like the real input: a blue Rhodia grid, pencil-grey
orthographic outlines, and a cartouche keyword in the upper-right corner.

Usage
-----
    python examples/generate_synthetic.py --out examples/scans --shape lbracket

Then run the pipeline on the result:

    python -m rhodia examples/scans -o examples/out.stl -vv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

PAGE = (1123, 794)  # A4 portrait @ ~96 dpi (h, w)
GRID_BGR = (235, 215, 195)   # light blue/violet (BGR)
PENCIL = (70, 70, 70)        # graphite grey


def _blank_page() -> np.ndarray:
    page = np.full((PAGE[0], PAGE[1], 3), 252, np.uint8)
    step = 16
    for x in range(0, PAGE[1], step):
        cv2.line(page, (x, 0), (x, PAGE[0]), GRID_BGR, 1)
    for y in range(0, PAGE[0], step):
        cv2.line(page, (0, y), (PAGE[1], y), GRID_BGR, 1)
    # Bolder major grid every 5 cells (classic Rhodia 5x5).
    for x in range(0, PAGE[1], step * 5):
        cv2.line(page, (x, 0), (x, PAGE[0]), (225, 200, 175), 1)
    for y in range(0, PAGE[0], step * 5):
        cv2.line(page, (0, y), (PAGE[1], y), (225, 200, 175), 1)
    return page


def _cartouche(page: np.ndarray, keyword: str) -> None:
    h, w = page.shape[:2]
    x0, y0 = int(w * 0.66), int(h * 0.03)
    cv2.rectangle(page, (x0, y0), (w - 30, y0 + 70), (120, 120, 120), 2)
    cv2.putText(page, keyword.upper(), (x0 + 12, y0 + 46),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, PENCIL, 2, cv2.LINE_AA)


def _draw_poly(page: np.ndarray, poly, jitter=1.2) -> None:
    """Draw a closed polyline with slight hand-drawn jitter."""
    pts = np.array(poly, np.float32)
    pts += np.random.normal(0, jitter, pts.shape)
    pts = pts.astype(np.int32)
    cv2.polylines(page, [pts], True, PENCIL, 2, cv2.LINE_AA)


# --- Shape library: each view is a polygon in a 300x300 local frame ---------
def lbracket_views():
    # An L-shaped bracket. width(X)=200, depth(Y)=120, height(Z)=200.
    L = [(0, 0), (200, 0), (200, 60), (60, 60), (60, 200), (0, 200)]  # X-Z (front)
    rect_xy = [(0, 0), (200, 0), (200, 120), (0, 120)]                # X-Y (top)
    rect_yz = [(0, 0), (120, 0), (120, 200), (0, 200)]                # Y-Z (right)
    return {"front": L, "top": rect_xy, "right": rect_yz}


def box_views():
    r_xz = [(0, 0), (180, 0), (180, 140), (0, 140)]
    r_xy = [(0, 0), (180, 0), (180, 100), (0, 100)]
    r_yz = [(0, 0), (100, 0), (100, 140), (0, 140)]
    return {"front": r_xz, "top": r_xy, "right": r_yz}


SHAPES = {"lbracket": lbracket_views, "box": box_views}


def render(views: dict, out: Path, with_detail: bool = False) -> None:
    out.mkdir(parents=True, exist_ok=True)
    offset = np.array([280, 360])  # place drawing on the page
    for name, poly in views.items():
        page = _blank_page()
        _cartouche(page, name)
        shifted = [(x + offset[0], y + offset[1]) for x, y in poly]
        _draw_poly(page, shifted)
        if with_detail and name == "front":
            # A red detail frame referencing a separate 'detail_hole' scan.
            cv2.rectangle(page, (offset[0] + 90, offset[1] + 80),
                          (offset[0] + 150, offset[1] + 140), (0, 0, 220), 2)
            cv2.putText(page, "detail_hole", (offset[0] + 60, offset[1] + 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 1, cv2.LINE_AA)
        cv2.imwrite(str(out / f"{name}.png"), page)
    print(f"Wrote {len(views)} scans to {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("examples/scans"))
    ap.add_argument("--shape", choices=list(SHAPES), default="lbracket")
    ap.add_argument("--with-detail", action="store_true")
    args = ap.parse_args()
    np.random.seed(0)
    render(SHAPES[args.shape](), args.out, args.with_detail)


if __name__ == "__main__":
    main()
