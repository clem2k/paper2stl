"""Main application window."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, Slot
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QSplitter, QStatusBar, QToolBar,
    QVBoxLayout, QWidget,
)

from rhodia.gui.panels.input_panel import InputPanel
from rhodia.gui.panels.params_panel import ParamsPanel
from rhodia.gui.widgets.log_view import LogView
from rhodia.gui.worker import PipelineWorker


class MainWindow(QMainWindow):
    """Top-level window: toolbar + left/right splitter + bottom log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: PipelineWorker | None = None
        self._tmp_dir: str | None = None
        self._settings = QSettings("Rhodia", "RhodiaGUI")
        self._build()
        self._restore_geometry()

    # ── construction ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setWindowTitle("Rhodia — Sketch to STL")
        self.setMinimumSize(900, 620)

        # ── toolbar ──────────────────────────────────────────────────────────
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setStyleSheet(
            "QToolBar { background: #fff; border-bottom: 1px solid #e5e7eb; "
            "padding: 6px 14px; spacing: 10px; }"
        )
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        logo = QLabel("<b style='font-size:15px;color:#2563eb;'>Rhodia</b>"
                      "<span style='font-size:11px;color:#9ca3af;'> &nbsp;sketch → STL</span>")
        tb.addWidget(logo)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # output path
        out_lbl = QLabel("Output:")
        out_lbl.setStyleSheet("font-size:12px; color:#6b7280;")
        tb.addWidget(out_lbl)

        self._out_edit = QLineEdit("output.stl")
        self._out_edit.setFixedWidth(200)
        self._out_edit.setPlaceholderText("output.stl")
        tb.addWidget(self._out_edit)

        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(28)
        browse_btn.setToolTip("Choose output file path")
        browse_btn.clicked.connect(self._browse_output)
        tb.addWidget(browse_btn)

        tb.addSeparator()

        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setObjectName("primary")
        self._run_btn.setToolTip("Start reconstruction  (Ctrl+R)")
        self._run_btn.clicked.connect(self._run)
        tb.addWidget(self._run_btn)

        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._run)

        # ── central widget: splitter ─────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # left panel
        self._input_panel = InputPanel()
        self._input_panel.setMinimumWidth(360)
        splitter.addWidget(self._input_panel)

        # right panel
        self._params_panel = ParamsPanel()
        self._params_panel.setMinimumWidth(320)
        splitter.addWidget(self._params_panel)

        splitter.setStretchFactor(0, 45)
        splitter.setStretchFactor(1, 55)
        splitter.setSizes([480, 560])
        root.addWidget(splitter, stretch=1)

        # ── bottom bar (progress + log) ──────────────────────────────────────
        bottom = QWidget()
        bottom.setStyleSheet("background: #fff; border-top: 1px solid #e5e7eb;")
        b_layout = QVBoxLayout(bottom)
        b_layout.setContentsMargins(12, 6, 12, 6)
        b_layout.setSpacing(4)

        prog_row = QHBoxLayout()
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet("font-size: 11px; color: #6b7280;")
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(6)
        prog_row.addWidget(self._progress, stretch=1)
        prog_row.addWidget(self._prog_lbl)
        b_layout.addLayout(prog_row)

        self._log = LogView()
        b_layout.addWidget(self._log)
        root.addWidget(bottom)

        # ── status bar ────────────────────────────────────────────────────────
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        sb.showMessage("Ready. Drop images onto the face cards to get started.")

    # ── output browse ─────────────────────────────────────────────────────────

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save STL as…",
            self._out_edit.text() or "output.stl",
            "STL files (*.stl)",
        )
        if path:
            self._out_edit.setText(path)

    # ── run / stop ────────────────────────────────────────────────────────────

    @Slot()
    def _run(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop()
            return

        paths = self._input_panel.get_view_paths()
        if not any(p for p in paths.values()):
            QMessageBox.warning(self, "No input", "Please add at least one face image.")
            return

        output_stl = self._out_edit.text().strip() or "output.stl"

        # Copy provided images into a temp folder named by view so the pipeline
        # can find them by filename (e.g. front.jpg, top.jpg …).
        if self._tmp_dir and Path(self._tmp_dir).exists():
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        self._tmp_dir = tempfile.mkdtemp(prefix="rhodia_")
        for view, src in paths.items():
            if src:
                suffix = Path(src).suffix
                dst = Path(self._tmp_dir) / f"{view}{suffix}"
                shutil.copy2(src, dst)

        cfg = self._params_panel.build_config()

        self._worker = PipelineWorker(cfg, self._tmp_dir, output_stl)
        self._worker.log_line.connect(self._log.append)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_success)
        self._worker.finished_err.connect(self._on_error)
        self._worker.start()

        self._run_btn.setText("■  Stop")
        self._run_btn.setToolTip("Stop the running reconstruction")
        self.statusBar().showMessage("Running…")
        self._log.clear()
        self._log.append(f"INFO rhodia.gui: Starting reconstruction → {output_stl}")

    def _stop(self) -> None:
        if self._worker:
            self._worker.terminate()
            self._worker.wait(2000)
        self._reset_run_btn()
        self.statusBar().showMessage("Stopped.")

    @Slot(int)
    def _on_progress(self, pct: int) -> None:
        self._progress.setValue(pct)
        if pct > 0:
            self._prog_lbl.setText(f"{pct}%")
        else:
            self._prog_lbl.setText("")

    @Slot(str)
    def _on_success(self, path: str) -> None:
        self._reset_run_btn()
        self.statusBar().showMessage(f"✓ STL written to {path}")
        self._log.append(f"INFO rhodia.gui: ✓ Done — {path}")
        reply = QMessageBox.question(
            self,
            "Reconstruction complete",
            f"STL written to:\n{path}\n\nOpen containing folder?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            _open_folder(path)

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._reset_run_btn()
        self.statusBar().showMessage(f"✗ Pipeline failed: {msg}")
        QMessageBox.critical(self, "Pipeline error", f"Reconstruction failed:\n\n{msg}")

    def _reset_run_btn(self) -> None:
        self._run_btn.setText("▶  Run")
        self._run_btn.setToolTip("Start reconstruction  (Ctrl+R)")
        self._progress.setValue(0)
        self._prog_lbl.setText("")

    # ── window state ──────────────────────────────────────────────────────────

    def _restore_geometry(self) -> None:
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Quit",
                "Reconstruction is running. Stop it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self._stop()
        self._settings.setValue("geometry", self.saveGeometry())
        if self._tmp_dir:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        event.accept()


# ── helpers ───────────────────────────────────────────────────────────────────

def _open_folder(stl_path: str) -> None:
    """Open the containing folder in the OS file manager."""
    folder = str(Path(stl_path).parent.resolve())
    import subprocess, sys
    if sys.platform == "win32":
        os.startfile(folder)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])
