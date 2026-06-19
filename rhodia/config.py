"""Typed configuration for the pipeline, loadable from YAML."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PreprocessConfig:
    # Rhodia grid lines are typically light blue/violet. We remove them in HSV.
    grid_hue_ranges: list[tuple[int, int]] = field(
        default_factory=lambda: [(90, 140)]  # cyan→violet band (OpenCV H in 0..179)
    )
    grid_min_saturation: int = 25
    # grid_tolerance: 0.0 = default; negative = stricter removal; positive = more
    # aggressive (expands hue range ±10 per unit, lowers sat threshold by 5 per unit).
    grid_tolerance: float = 0.0
    pencil_block_size: int = 35      # adaptive threshold window (odd)
    pencil_C: int = 10               # adaptive threshold bias
    hough_threshold: int = 50
    hough_min_line_length: int = 40
    hough_max_line_gap: int = 8
    line_merge_angle_deg: float = 5.0
    line_merge_dist_px: float = 12.0
    # line_straighten_pct: 100 = full TLS refit (perfectly straight, default);
    # 0 = keep raw Hough endpoints (preserves curves/wobble).
    line_straighten_pct: float = 100.0


@dataclass
class MetadataConfig:
    ocr_backend: str = "auto"        # auto | easyocr | tesseract | none
    cartouche_frac: tuple[float, float] = (0.62, 0.18)  # (x_start, height) fractions
    red_hue_ranges: list[tuple[int, int]] = field(
        default_factory=lambda: [(0, 10), (170, 179)]
    )
    red_min_saturation: int = 90
    red_min_value: int = 60
    red_min_box_area_frac: float = 0.002


@dataclass
class ReconstructionConfig:
    voxel_resolution: int = 128      # cells along the longest axis
    fill_missing: bool = True        # mirror opposite views, extrude singles
    default_extrude_frac: float = 0.5  # depth for a lone view (frac of view size)
    # Photogrammetry-style cross-view registration: drawings placed differently
    # on each sheet are realigned by correlating their 1-D projection profiles
    # along every shared world axis, with a uniform (proportion-preserving) scale
    # consensus instead of a naive per-axis stretch.
    align_views: bool = True
    # How far a view may be nudged to register, as a fraction of the axis length.
    # Higher = tolerates larger misalignment between sheets (search further);
    # lower = stricter, trusts the drawn position more. 0 disables the shift
    # search (uniform-scale consensus only).
    align_tolerance: float = 0.15
    use_neural_completion: bool = False
    neural_weights: str | None = None
    marching_cubes_level: float = 0.5
    smoothing_iterations: int = 5


@dataclass
class ExportConfig:
    stl_binary: bool = True
    target_size_mm: float | None = None   # rescale longest dim to this many mm
    ensure_watertight: bool = True


@dataclass
class PipelineConfig:
    device: str | None = None         # None → auto (cuda>mps>cpu)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
    reconstruction: ReconstructionConfig = field(default_factory=ReconstructionConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    # If set, per-page debug images (grid removal, binary, segments, silhouette)
    # are written as JPEGs into this directory.
    debug_dir: str | None = None

    # ---- (de)serialisation -------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineConfig":
        def build(klass, payload):
            payload = payload or {}
            fields = {f.name: f for f in dataclasses.fields(klass)}
            kwargs = {}
            for key, val in payload.items():
                if key not in fields:
                    continue
                # tuples come back from yaml as lists; coerce where declared.
                kwargs[key] = tuple(val) if isinstance(val, list) and "tuple" in str(
                    fields[key].type
                ) else val
            return klass(**kwargs)

        return cls(
            device=data.get("device"),
            preprocess=build(PreprocessConfig, data.get("preprocess")),
            metadata=build(MetadataConfig, data.get("metadata")),
            reconstruction=build(ReconstructionConfig, data.get("reconstruction")),
            export=build(ExportConfig, data.get("export")),
            debug_dir=data.get("debug_dir"),
        )

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
