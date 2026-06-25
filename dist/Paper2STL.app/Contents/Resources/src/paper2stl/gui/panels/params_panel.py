"""Right panel: all pipeline parameters in collapsible sections."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from paper2stl.config import (
    ExportConfig, MetadataConfig, PreprocessConfig, PipelineConfig,
    ReconstructionConfig,
)
from paper2stl.gui.widgets.param_row import (
    BoolRow, ChoiceRow, FloatRow, IntRow, OptionalFloatRow, OptionalPathRow,
)
from paper2stl.gui.widgets.section import CollapsibleSection


class ParamsPanel(QWidget):
    """Scrollable panel exposing every pipeline parameter.

    Call ``build_config()`` to get a ``PipelineConfig`` populated from the
    current widget state.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, object] = {}
        self._build()

    # ── layout ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        for section_fn in (
            self._section_device,
            self._section_grid,
            self._section_pencil,
            self._section_lines,
            self._section_regularize,
            self._section_reconstruction,
            self._section_export,
            self._section_debug,
        ):
            lay.addWidget(section_fn())
        lay.addStretch()

    def _r(self, key: str, widget) -> object:
        """Register a parameter row under *key* and return it."""
        self._rows[key] = widget
        return widget

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sec(title: str, rows: list, expanded: bool = True) -> CollapsibleSection:
        sec = CollapsibleSection(title, expanded=expanded)
        for w in rows:
            sec.add_widget(w)
        return sec

    # ── sections ─────────────────────────────────────────────────────────────

    def _section_device(self) -> CollapsibleSection:
        return self._sec("Device & OCR", [
            self._r("device", ChoiceRow(
                "Compute device",
                ["auto", "cuda", "mps", "cpu"],
                default="auto",
                tooltip="GPU backend for neural features. 'auto' picks CUDA > MPS > CPU.",
            )),
            self._r("ocr_backend", ChoiceRow(
                "OCR backend",
                ["auto", "none", "easyocr", "tesseract"],
                default="none",
                tooltip=(
                    "'none' skips OCR and classifies views by filename — fastest. "
                    "'auto' tries EasyOCR then Tesseract."
                ),
            )),
        ])

    def _section_grid(self) -> CollapsibleSection:
        return self._sec("Grid Removal", [
            self._r("grid_tolerance", FloatRow(
                "Tolerance",
                minimum=-3.0, maximum=3.0, step=0.1, default=0.0, decimals=1,
                tooltip=(
                    "Aggressiveness of grid removal. "
                    "0 = default; +1 removes more (expand hue ±10, lower sat threshold); "
                    "-1 removes less. Use positive values for stubborn faint grids."
                ),
            )),
            self._r("grid_min_saturation", IntRow(
                "Min saturation",
                minimum=5, maximum=80, step=1, default=25,
                tooltip="Minimum HSV saturation for a pixel to be considered grid (0–255 scale mapped to 0–80).",
            )),
            self._r("grid_max_value", IntRow(
                "Max brightness",
                minimum=100, maximum=255, step=5, default=180,
                tooltip=(
                    "Only pixels brighter than this are treated as grid. "
                    "Protects dark pencil strokes from being inpainted away. "
                    "Default 180 is well above any pencil mark."
                ),
            )),
        ], expanded=False)

    def _section_pencil(self) -> CollapsibleSection:
        return self._sec("Pencil Extraction", [
            self._r("pencil_min_strength", IntRow(
                "Min contrast (strength)",
                minimum=0, maximum=100, step=1, default=55,
                tooltip=(
                    "How much darker than the local paper background a pixel "
                    "must be to count as pencil. "
                    "Higher = rejects more faint grid; lower = keeps fainter strokes. "
                    "0 = legacy adaptive threshold method."
                ),
            )),
            self._r("pencil_bg_kernel", IntRow(
                "Background kernel (px)",
                minimum=5, maximum=99, step=2, default=25,
                tooltip="Size of morphological closing kernel used to estimate the paper background. Larger = smoother background estimation.",
            )),
            self._r("pencil_block_size", IntRow(
                "Adaptive block size",
                minimum=11, maximum=99, step=2, default=35,
                tooltip="Window size for legacy adaptive threshold (only when strength=0). Must be odd.",
            )),
            self._r("pencil_C", IntRow(
                "Adaptive bias C",
                minimum=-20, maximum=40, step=1, default=10,
                tooltip="Constant subtracted from adaptive threshold mean (legacy method).",
            )),
        ], expanded=False)

    def _section_lines(self) -> CollapsibleSection:
        return self._sec("Line Detection & Merging", [
            self._r("hough_threshold", IntRow(
                "Hough threshold",
                minimum=10, maximum=200, step=5, default=50,
                tooltip="Minimum vote count for a Hough line to be detected. Lower = more sensitive but noisier.",
            )),
            self._r("hough_min_line_length", IntRow(
                "Min line length (px)",
                minimum=5, maximum=200, step=5, default=40,
                tooltip="Shortest segment Hough will report. Set lower to catch short dashes.",
            )),
            self._r("hough_max_line_gap", IntRow(
                "Max dash gap (px)",
                minimum=1, maximum=80, step=1, default=8,
                tooltip="Largest gap in a dashed line still merged into one segment. Raise to bridge wider gaps.",
            )),
            self._r("line_merge_angle_deg", FloatRow(
                "Merge angle (°)",
                minimum=0.0, maximum=20.0, step=0.5, default=5.0, decimals=1,
                tooltip="Segments whose directions differ by less than this are considered collinear and merged.",
            )),
            self._r("line_merge_dist_px", FloatRow(
                "Merge distance (px)",
                minimum=1.0, maximum=60.0, step=1.0, default=12.0, decimals=1,
                tooltip="Maximum perpendicular distance between collinear segments for them to be merged.",
            )),
            self._r("line_straighten_pct", FloatRow(
                "Straighten %",
                minimum=0.0, maximum=100.0, step=5.0, default=100.0, decimals=0,
                tooltip=(
                    "How much to straighten each line cluster via TLS refit. "
                    "100 = fully straight (default); 0 = raw Hough endpoints (preserves curves). "
                    "Intermediate values blend the two."
                ),
            )),
        ], expanded=False)

    def _section_regularize(self) -> CollapsibleSection:
        return self._sec("Shape Regularisation", [
            self._r("regularize_shapes", BoolRow(
                "Enable regularisation",
                default=True,
                tooltip=(
                    "Clean the filled silhouette as a geometric primitive: "
                    "near-rectangles become perfect rectangles; other outlines have "
                    "their edges snapped to dominant angles. Eliminates waves on flat faces."
                ),
            )),
            self._r("regularize_rect_score", FloatRow(
                "Rectangle score",
                minimum=0.50, maximum=1.00, step=0.01, default=0.90, decimals=2,
                tooltip=(
                    "Minimum 'rectangleness' (area / bounding-rectangle area) "
                    "to collapse a shape into a perfect rectangle. "
                    "0.90 = anything that looks 90% like a rectangle becomes one."
                ),
            )),
            self._r("regularize_angle_snap_deg", FloatRow(
                "Angle snap (°)",
                minimum=0.0, maximum=45.0, step=0.5, default=10.0, decimals=1,
                tooltip="Edges within this many degrees of a dominant axis are snapped to exactly that angle.",
            )),
            self._r("regularize_derotate_max_deg", FloatRow(
                "De-rotate max (°)",
                minimum=0.0, maximum=45.0, step=1.0, default=12.0, decimals=0,
                tooltip=(
                    "Remove sheet tilt up to this many degrees to make the part axis-aligned. "
                    "Larger intentional rotations are kept."
                ),
            )),
            self._r("regularize_poly_epsilon_frac", FloatRow(
                "Poly simplify ε",
                minimum=0.0, maximum=0.05, step=0.001, default=0.01, decimals=3,
                tooltip="approxPolyDP epsilon as fraction of perimeter. Higher = fewer vertices before snapping.",
            )),
        ], expanded=True)

    def _section_reconstruction(self) -> CollapsibleSection:
        return self._sec("Reconstruction", [
            self._r("voxel_resolution", IntRow(
                "Voxel resolution",
                minimum=32, maximum=512, step=16, default=256,
                tooltip="Grid cells along the longest axis. Higher = more detail; 256 is the recommended default.",
            )),
            self._r("fill_missing", BoolRow(
                "Fill missing views",
                default=True,
                tooltip="Mirror opposite views if one is not provided; extrude single views to a finite slab.",
            )),
            self._r("default_extrude_frac", FloatRow(
                "Extrude depth (frac)",
                minimum=0.1, maximum=1.0, step=0.05, default=0.5, decimals=2,
                tooltip="Depth of a lone view as a fraction of its in-plane extent (when mirroring).",
            )),
            self._r("align_views", BoolRow(
                "Align views",
                default=True,
                tooltip=(
                    "Cross-view registration: correlate projection profiles to correct "
                    "for drawings placed at different positions on each sheet."
                ),
            )),
            self._r("align_tolerance", FloatRow(
                "Align tolerance",
                minimum=0.0, maximum=0.5, step=0.01, default=0.15, decimals=2,
                tooltip="How far a view may be nudged as a fraction of the axis length. 0 = scale-only, no shift.",
            )),
            self._r("marching_cubes_level", FloatRow(
                "Marching cubes level",
                minimum=0.1, maximum=0.9, step=0.05, default=0.5, decimals=2,
                tooltip="Isosurface threshold for marching cubes. 0.5 is standard for a binary occupancy grid.",
            )),
            self._r("smoothing_iterations", IntRow(
                "Taubin smoothing",
                minimum=0, maximum=20, step=1, default=5,
                tooltip="Iterations of volume-preserving Taubin smoothing applied after meshing. 0 = off.",
            )),
        ], expanded=True)

    def _section_export(self) -> CollapsibleSection:
        return self._sec("Export", [
            self._r("target_size_mm", OptionalFloatRow(
                "Target size (mm)",
                minimum=1.0, maximum=5000.0, step=10.0,
                default=None, unit="mm",
                tooltip="Rescale the STL so its longest dimension equals this value. Leave unchecked to keep raw voxel units.",
            )),
            self._r("stl_binary", BoolRow(
                "Binary STL",
                default=True,
                tooltip="Write binary STL (compact) rather than ASCII.",
            )),
            self._r("ensure_watertight", BoolRow(
                "Ensure watertight",
                default=True,
                tooltip="Run trimesh repair pass to close holes and fix normals.",
            )),
            self._r("presmooth_sigma", FloatRow(
                "Pre-smooth σ (voxels)",
                minimum=0.0, maximum=3.0, step=0.1, default=0.6, decimals=1,
                tooltip=(
                    "Gaussian blur of the occupancy grid before marching cubes. "
                    "Reduces voxel staircase artefacts on flat faces. "
                    "0 = off; 0.6 is the recommended default."
                ),
            )),
        ], expanded=False)

    def _section_debug(self) -> CollapsibleSection:
        return self._sec("Debug Output", [
            self._r("debug_dir", OptionalPathRow(
                "Debug image folder",
                default=None,
                tooltip=(
                    "If set, saves 5 JPEG debug images per view into this folder: "
                    "grid-removed, binary, segments overlay, raw silhouette, "
                    "and regularised silhouette."
                ),
            )),
        ], expanded=False)

    # ── config extraction ────────────────────────────────────────────────────

    def _v(self, key: str):
        row = self._rows[key]
        return row.get_value()

    def build_config(self) -> PipelineConfig:
        """Build and return a ``PipelineConfig`` from the current widget state."""
        device_val = self._v("device")

        pre = PreprocessConfig(
            grid_tolerance            = self._v("grid_tolerance"),
            grid_min_saturation       = self._v("grid_min_saturation"),
            grid_max_value            = self._v("grid_max_value"),
            pencil_min_strength       = self._v("pencil_min_strength"),
            pencil_bg_kernel          = self._v("pencil_bg_kernel"),
            pencil_block_size         = self._v("pencil_block_size"),
            pencil_C                  = self._v("pencil_C"),
            hough_threshold           = self._v("hough_threshold"),
            hough_min_line_length     = self._v("hough_min_line_length"),
            hough_max_line_gap        = self._v("hough_max_line_gap"),
            line_merge_angle_deg      = self._v("line_merge_angle_deg"),
            line_merge_dist_px        = self._v("line_merge_dist_px"),
            line_straighten_pct       = self._v("line_straighten_pct"),
            regularize_shapes         = self._v("regularize_shapes"),
            regularize_rect_score     = self._v("regularize_rect_score"),
            regularize_angle_snap_deg = self._v("regularize_angle_snap_deg"),
            regularize_derotate_max_deg = self._v("regularize_derotate_max_deg"),
            regularize_poly_epsilon_frac = self._v("regularize_poly_epsilon_frac"),
        )

        meta = MetadataConfig(
            ocr_backend = self._v("ocr_backend"),
        )

        rec = ReconstructionConfig(
            voxel_resolution     = self._v("voxel_resolution"),
            fill_missing         = self._v("fill_missing"),
            default_extrude_frac = self._v("default_extrude_frac"),
            align_views          = self._v("align_views"),
            align_tolerance      = self._v("align_tolerance"),
            marching_cubes_level = self._v("marching_cubes_level"),
            smoothing_iterations = self._v("smoothing_iterations"),
        )

        exp = ExportConfig(
            target_size_mm   = self._v("target_size_mm"),
            stl_binary       = self._v("stl_binary"),
            ensure_watertight = self._v("ensure_watertight"),
            presmooth_sigma  = self._v("presmooth_sigma"),
        )

        return PipelineConfig(
            device      = None if device_val == "auto" else device_val,
            preprocess  = pre,
            metadata    = meta,
            reconstruction = rec,
            export      = exp,
            debug_dir   = self._v("debug_dir"),
        )
