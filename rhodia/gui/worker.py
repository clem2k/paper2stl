"""Background QThread that runs the Rhodia pipeline without freezing the UI."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class _GuiLogHandler(logging.Handler):
    """Logging handler that emits records to a Qt signal."""

    def __init__(self, signal: Signal):
        super().__init__()
        self._signal = signal
        fmt = logging.Formatter("%(levelname)s %(name)s: %(message)s")
        self.setFormatter(fmt)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._signal.emit(self.format(record))
        except Exception:
            pass


class PipelineWorker(QThread):
    """Run the Rhodia pipeline in a background thread.

    Signals
    -------
    log_line : str
        A formatted log message; connect to the log widget's append slot.
    progress : int
        Overall progress percentage (0–100).
    finished_ok : str
        Emitted with the output STL path when the pipeline succeeds.
    finished_err : str
        Emitted with the error message when the pipeline fails.
    """

    log_line     = Signal(str)
    progress     = Signal(int)
    finished_ok  = Signal(str)
    finished_err = Signal(str)

    def __init__(self, cfg, input_dir: str | Path, output_stl: str | Path):
        super().__init__()
        self._cfg        = cfg
        self._input_dir  = Path(input_dir)
        self._output_stl = Path(output_stl)
        self._handler: _GuiLogHandler | None = None

    # ── internal helpers ────────────────────────────────────────────────────

    def _install_log(self) -> None:
        self._handler = _GuiLogHandler(self.log_line)
        self._handler.setLevel(logging.DEBUG)
        logging.getLogger("rhodia").addHandler(self._handler)
        logging.getLogger("rhodia").setLevel(logging.INFO)

    def _remove_log(self) -> None:
        if self._handler:
            logging.getLogger("rhodia").removeHandler(self._handler)
            self._handler = None

    # ── QThread entry point ─────────────────────────────────────────────────

    def run(self) -> None:
        self._install_log()
        try:
            from rhodia.pipeline import Pipeline

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
            from rhodia.utils.io import list_images
            images = list(list_images(self._input_dir))
            total_hint[0] = max(1, len(images))
            pipeline.process_page = _tracked

            out = pipeline.run(self._input_dir, self._output_stl)
            self.progress.emit(100)
            self.finished_ok.emit(str(out))

        except Exception as exc:
            tb = traceback.format_exc()
            self.log_line.emit(f"ERROR: {exc}\n{tb}")
            self.finished_err.emit(str(exc))
        finally:
            self._remove_log()
            self.progress.emit(0)
