"""Background QThread that runs the Paper2STL pipeline without freezing the UI."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class PipelineWorker(QThread):
    """Run the Paper2STL pipeline in a background thread.

    Signals
    -------
    progress : int
        Overall progress percentage (0–100).
    finished_ok : str
        Emitted with the output STL path when the pipeline succeeds.
    finished_err : str
        Emitted with the error message when the pipeline fails.

    Log output is captured by the global _AppLogHandler installed in MainWindow.
    """

    progress     = Signal(int)
    finished_ok  = Signal(str)
    finished_err = Signal(str)

    def __init__(self, cfg, input_dir: str | Path, output_stl: str | Path):
        super().__init__()
        self._cfg        = cfg
        self._input_dir  = Path(input_dir)
        self._output_stl = Path(output_stl)

    # ── QThread entry point ─────────────────────────────────────────────────

    def run(self) -> None:
        logging.getLogger("paper2stl").setLevel(logging.INFO)
        try:
            from paper2stl.pipeline import Pipeline

            self.progress.emit(5)
            pipeline = Pipeline(self._cfg)
            self.progress.emit(10)

            # Monkey-patch process_page to emit progress per view
            original = pipeline.process_page
            processed = [0]
            total_hint = [6]  # rough estimate; updated after first page

            def _tracked(path):
                result = original(path)
                processed[0] += 1
                pct = 10 + int(70 * processed[0] / max(1, total_hint[0]))
                self.progress.emit(min(pct, 79))
                return result

            # Count images first for accurate progress
            from paper2stl.utils.io import list_images
            images = list(list_images(self._input_dir))
            total_hint[0] = max(1, len(images))
            pipeline.process_page = _tracked

            out = pipeline.run(self._input_dir, self._output_stl)
            self.progress.emit(100)
            self.finished_ok.emit(str(out))

        except Exception as exc:
            tb = traceback.format_exc()
            logging.getLogger("paper2stl").error("Pipeline failed: %s\n%s", exc, tb)
            self.finished_err.emit(str(exc))
        finally:
            self.progress.emit(0)
