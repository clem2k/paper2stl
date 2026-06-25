"""Command-line interface: ``python -m paper2stl ...``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import PipelineConfig
from .device import describe
from .pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paper2stl",
        description="Reconstruct an STL from orthographic pencil sketches on "
        "grid paper.",
    )
    p.add_argument("input", type=Path, nargs="?", default=None,
                   help="folder of scan images (not required when --gui is used)")
    p.add_argument(
        "-o", "--output", type=Path, default=Path("output.stl"),
        help="output STL path (default: output.stl)",
    )
    p.add_argument("-c", "--config", type=Path, help="YAML config file")
    p.add_argument(
        "--device", choices=["cuda", "mps", "cpu"], help="force compute device"
    )
    p.add_argument(
        "--resolution", type=int, help="voxel grid resolution (longest axis)"
    )
    p.add_argument(
        "--no-fill-missing", action="store_true",
        help="disable mirroring of missing opposite views",
    )
    p.add_argument(
        "--no-align", action="store_true",
        help="disable photogrammetry-style cross-view registration "
        "(fall back to crop-and-stretch placement)",
    )
    p.add_argument(
        "--align-tolerance", type=float, metavar="FRAC", default=None,
        help="how far a view may be nudged to register, as a fraction of the "
        "axis length (default 0.15). Higher tolerates larger per-sheet "
        "misalignment; 0 disables the shift search.",
    )
    p.add_argument(
        "--neural-weights", type=Path,
        help="enable neural completion with these weights",
    )
    p.add_argument("--size-mm", type=float, help="rescale longest dim to N mm")
    p.add_argument(
        "--ocr-backend", choices=["auto", "easyocr", "tesseract", "none"],
        default=None,
        help=(
            "view-label OCR backend (default auto). Use 'none' to skip OCR "
            "entirely and classify views by file name only — much faster, and "
            "all that is needed when scans are named front/top/back/etc."
        ),
    )
    p.add_argument(
        "--grid-tolerance", type=float, metavar="N", default=None,
        help=(
            "grid removal tolerance (default 0.0); negative = stricter, "
            "positive = more aggressive. Each unit expands the hue range by "
            "±10, lowers the saturation floor by 5 and raises the pencil "
            "contrast floor by 8."
        ),
    )
    p.add_argument(
        "--pencil-strength", type=int, metavar="N", default=None,
        help=(
            "ink contrast floor: how much darker than the paper a stroke must "
            "be to count as pencil (default 55). Higher rejects more faint grid; "
            "lower keeps fainter strokes. 0 = legacy adaptive-threshold method."
        ),
    )
    p.add_argument(
        "--straighten-pct", type=float, metavar="PCT", default=None,
        help=(
            "line straightening percentage 0–100 (default 100). "
            "100 = fully straightened via TLS refit; "
            "0 = raw Hough endpoints kept (preserves curves/wobble); "
            "intermediate values blend the two."
        ),
    )
    p.add_argument(
        "--no-regularize", action="store_true",
        help="disable aggressive geometric regularisation of silhouettes "
        "(keep the raw hand-drawn outline instead of snapping to clean "
        "rectangles / straight edges)",
    )
    p.add_argument(
        "--rect-score", type=float, metavar="FRAC", default=None,
        help="rectangleness threshold 0–1 (default 0.90): a silhouette filling "
        "at least this fraction of its bounding rectangle is collapsed to a "
        "perfect rectangle. Lower = more shapes snap to rectangles.",
    )
    p.add_argument(
        "--angle-snap-deg", type=float, metavar="DEG", default=None,
        help="snap silhouette edges within this many degrees of a dominant "
        "axis to exactly straight (default 10). Higher = more aggressive.",
    )
    p.add_argument(
        "--presmooth-sigma", type=float, metavar="SIGMA", default=None,
        help="Gaussian pre-smoothing (voxels) of the grid before marching "
        "cubes (default 0.6). 0 disables it; higher smooths more.",
    )
    p.add_argument(
        "--debug-dir", type=Path, metavar="DIR", default=None,
        help=(
            "save per-page debug images (grid removal, binary strokes, "
            "detected segments, silhouette) as JPEGs into DIR"
        ),
    )
    p.add_argument("-v", "--verbose", action="count", default=0)
    p.add_argument("--info", action="store_true", help="print device info and exit")
    p.add_argument("--gui",  action="store_true",
                   help="launch the graphical interface (same as python -m paper2stl.gui)")
    return p


def _apply_overrides(cfg: PipelineConfig, args) -> PipelineConfig:
    if args.device:
        cfg.device = args.device
    if args.resolution:
        cfg.reconstruction.voxel_resolution = args.resolution
    if args.no_fill_missing:
        cfg.reconstruction.fill_missing = False
    if args.no_align:
        cfg.reconstruction.align_views = False
    if args.align_tolerance is not None:
        cfg.reconstruction.align_tolerance = args.align_tolerance
    if args.neural_weights:
        cfg.reconstruction.use_neural_completion = True
        cfg.reconstruction.neural_weights = str(args.neural_weights)
    if args.size_mm:
        cfg.export.target_size_mm = args.size_mm
    if args.ocr_backend is not None:
        cfg.metadata.ocr_backend = args.ocr_backend
    if args.grid_tolerance is not None:
        cfg.preprocess.grid_tolerance = args.grid_tolerance
    if args.pencil_strength is not None:
        cfg.preprocess.pencil_min_strength = args.pencil_strength
    if args.straighten_pct is not None:
        cfg.preprocess.line_straighten_pct = args.straighten_pct
    if args.no_regularize:
        cfg.preprocess.regularize_shapes = False
    if args.rect_score is not None:
        cfg.preprocess.regularize_rect_score = args.rect_score
    if args.angle_snap_deg is not None:
        cfg.preprocess.regularize_angle_snap_deg = args.angle_snap_deg
    if args.presmooth_sigma is not None:
        cfg.export.presmooth_sigma = args.presmooth_sigma
    if args.debug_dir is not None:
        cfg.debug_dir = str(args.debug_dir)
    return cfg


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.gui:
        from paper2stl.gui import run_gui
        return run_gui()

    level = logging.WARNING - 10 * min(args.verbose, 2)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    if args.info:
        print(describe())
        return 0

    if not args.input:
        build_parser().error("the following arguments are required: input")

    cfg = PipelineConfig.from_yaml(args.config) if args.config else PipelineConfig()
    cfg = _apply_overrides(cfg, args)

    pipeline = Pipeline(cfg)
    try:
        out = pipeline.run(args.input, args.output)
    except Exception as exc:  # surface a clean message, full trace at -vv
        logging.getLogger("paper2stl").error("Pipeline failed: %s", exc, exc_info=args.verbose >= 2)
        return 1
    print(f"✓ STL written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
