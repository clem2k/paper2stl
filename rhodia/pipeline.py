"""End-to-end orchestrator: a folder of scans → one STL file.

Stages (each delegated to its module so they remain independently testable):

    A. preprocessing   grid removal → pencil binarisation → vectorisation
    B. metadata        view classification (OCR) + red detail-frame detection
    C. reconstruction  register views → complete missing → voxel visual hull
       detail pages    stamp referenced detail features onto faces
    D. export          marching cubes → watertight repair → STL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import PipelineConfig
from .detail_pages import DetailPage, apply_detail_pages
from .device import describe, get_device
from .metadata import OCREngine, classify_view, detect_red_frames
from .metadata.ocr import match_view
from .preprocessing import extract_pencil, remove_grid, vectorize_lines
from .preprocessing.vectorize import rasterize_silhouette
from .reconstruction import ViewSilhouette, reconstruct
from .export import export_stl, occupancy_to_mesh
from .utils.io import list_images, read_image

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    """Per-scan intermediate result."""

    path: Path
    view: str | None
    confidence: float
    silhouette: np.ndarray
    references: list = field(default_factory=list)  # DetailReference


class Pipeline:
    def __init__(self, config: PipelineConfig | None = None):
        self.cfg = config or PipelineConfig()
        self.device = get_device(self.cfg.device)
        self.ocr = OCREngine(self.cfg.metadata.ocr_backend, self.device)
        logger.info("Rhodia pipeline initialised — %s", describe())

    # ----- Stage A + B : process a single scan -----------------------------
    def process_page(self, path: str | Path) -> PageResult:
        """Run preprocessing + metadata extraction on one scan."""
        path = Path(path)
        bgr = read_image(path)

        # A. Pre-processing
        gray = remove_grid(bgr, self.cfg.preprocess)
        binary = extract_pencil(gray, self.cfg.preprocess)
        # The cartouche text/box are pencil strokes too — exclude that corner
        # so it does not pollute the part silhouette.
        self._blank_cartouche(binary)
        segments = vectorize_lines(binary, self.cfg.preprocess)
        silhouette = rasterize_silhouette(segments, binary.shape)

        # B. Metadata
        view, conf = classify_view(bgr, self.ocr, self.cfg.metadata)
        if view is None:
            # Fallback: derive the view from the filename (e.g. 'front.png').
            view, conf = match_view(path.stem)
            if view is not None:
                conf *= 0.9  # filename is a weaker signal than the cartouche
                logger.info("View for %s taken from filename → %s", path.name, view)
        refs = detect_red_frames(bgr, self.ocr, self.cfg.metadata)

        logger.info(
            "Page %s → view=%s (conf=%.2f), %d segments, %d detail refs",
            path.name, view, conf, len(segments), len(refs),
        )
        return PageResult(path, view, conf, silhouette, refs)

    def _blank_cartouche(self, binary: np.ndarray) -> None:
        """Zero the upper-right cartouche region in-place."""
        h, w = binary.shape[:2]
        x0 = int(w * self.cfg.metadata.cartouche_frac[0])
        y1 = int(h * self.cfg.metadata.cartouche_frac[1])
        binary[0:y1, x0:w] = 0

    # ----- Whole-folder run ------------------------------------------------
    def run(
        self,
        input_dir: str | Path,
        output_stl: str | Path,
        detail_pages: list[DetailPage] | None = None,
    ) -> Path:
        """Process every scan in *input_dir* and export an STL."""
        pages = [self.process_page(p) for p in list_images(input_dir)]
        return self._reconstruct_and_export(pages, output_stl, detail_pages)

    def run_on_silhouettes(
        self,
        silhouettes: dict[str, np.ndarray],
        output_stl: str | Path,
        detail_pages: list[DetailPage] | None = None,
    ) -> Path:
        """Reconstruct directly from named silhouettes (skips stages A/B).

        Handy for testing and for callers that already have clean views.
        """
        views = [ViewSilhouette(name=k, mask=v) for k, v in silhouettes.items()]
        occupancy, _ = reconstruct(views, self.cfg.reconstruction)
        if detail_pages:
            occupancy = apply_detail_pages(occupancy, detail_pages)
        mesh = occupancy_to_mesh(
            occupancy,
            self.cfg.export,
            self.cfg.reconstruction.smoothing_iterations,
            self.cfg.reconstruction.marching_cubes_level,
        )
        return export_stl(mesh, output_stl, self.cfg.export.stl_binary)

    # ----- Stage C + D -----------------------------------------------------
    def _reconstruct_and_export(
        self, pages: list[PageResult], output_stl, detail_pages
    ) -> Path:
        # Keep the highest-confidence page per view when duplicates appear.
        best: dict[str, PageResult] = {}
        for pg in pages:
            if pg.view is None:
                logger.warning("Skipping %s: no view classified", pg.path.name)
                continue
            if pg.view not in best or pg.confidence > best[pg.view].confidence:
                best[pg.view] = pg

        if not best:
            raise RuntimeError(
                "No usable views detected. Check OCR backend / cartouche region."
            )

        views = [ViewSilhouette(p.view, p.silhouette, p.confidence) for p in best.values()]
        occupancy, bbox = reconstruct(views, self.cfg.reconstruction)
        logger.info("Reconstructed within %s", bbox)

        details = list(detail_pages or [])
        details += self._resolve_detail_references(pages)
        if details:
            occupancy = apply_detail_pages(occupancy, details)

        mesh = occupancy_to_mesh(
            occupancy,
            self.cfg.export,
            self.cfg.reconstruction.smoothing_iterations,
            self.cfg.reconstruction.marching_cubes_level,
        )
        return export_stl(mesh, output_stl, self.cfg.export.stl_binary)

    def _resolve_detail_references(self, pages: list[PageResult]) -> list[DetailPage]:
        """Match red-frame references to detail scans and build DetailPages.

        A reference text is matched (case-insensitive substring) against the
        filename / classified view of other scans.  Matched detail scans become
        pocket features placed at the red frame's location on the owning face.
        """
        by_name = {p.path.stem.lower(): p for p in pages}
        details: list[DetailPage] = []
        for pg in pages:
            if pg.view is None:
                continue
            for ref in pg.references:
                token = ref.text.lower().strip()
                if not token:
                    continue
                match = next(
                    (p for stem, p in by_name.items() if token in stem and p is not pg),
                    None,
                )
                if match is None:
                    logger.warning("Detail ref '%s' on %s unresolved", token, pg.path.name)
                    continue
                details.append(
                    DetailPage(
                        target_view=pg.view,
                        mask=match.silhouette,
                        mode="pocket",
                        region=(ref.center_norm[0], ref.center_norm[1], 0.3, 0.3),
                    )
                )
                logger.info("Resolved detail '%s' onto %s face", token, pg.view)
        return details
