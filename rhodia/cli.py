"""Command-line interface: ``python -m rhodia ...``."""

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
        prog="rhodia",
        description="Reconstruct an STL from orthographic pencil sketches on "
        "Rhodia grid paper.",
    )
    p.add_argument("input", type=Path, help="folder of scan images")
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
        "--grid-tolerance", type=float, metavar="N", default=None,
        help=(
            "grid removal tolerance (default 0.0); negative = stricter, "
            "positive = more aggressive. Each unit expands the hue range by "
            "±10 and lowers the saturation floor by 5."
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
        "--debug-dir", type=Path, metavar="DIR", default=None,
        help=(
            "save per-page debug images (grid removal, binary strokes, "
            "detected segments, silhouette) as JPEGs into DIR"
        ),
    )
    p.add_argument("-v", "--verbose", action="count", default=0)
    p.add_argument("--info", action="store_true", help="print device info and exit")
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
    if args.grid_tolerance is not None:
        cfg.preprocess.grid_tolerance = args.grid_tolerance
    if args.straighten_pct is not None:
        cfg.preprocess.line_straighten_pct = args.straighten_pct
    if args.debug_dir is not None:
        cfg.debug_dir = str(args.debug_dir)
    return cfg


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = logging.WARNING - 10 * min(args.verbose, 2)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    if args.info:
        print(describe())
        return 0

    cfg = PipelineConfig.from_yaml(args.config) if args.config else PipelineConfig()
    cfg = _apply_overrides(cfg, args)

    pipeline = Pipeline(cfg)
    try:
        out = pipeline.run(args.input, args.output)
    except Exception as exc:  # surface a clean message, full trace at -vv
        logging.getLogger("rhodia").error("Pipeline failed: %s", exc, exc_info=args.verbose >= 2)
        return 1
    print(f"✓ STL written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
