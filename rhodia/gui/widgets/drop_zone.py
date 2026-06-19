"""Per-view image drop zone widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QHBoxLayout, QWidget,
)

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

VIEW_LABELS = {
    "front":  "Front",
    "rear":   "Rear / Back",
    "top":    "Top",
    "bottom": "Bottom",
    "left":   "Left",
    "right":  "Right",
}

VIEW_ICONS = {
    "front":  "↑ ·",
    "rear":   "· ↓",
    "top":    "⊙",
    "bottom": "⊗",
    "left":   "← ·",
    "right":  "· →",
}


class ViewDropZone(QFrame):
    """Drag-and-drop (or click-to-browse) card for one orthographic view.

    Signals
    -------
    file_changed : str or None
        Emits the new path when an image is dropped/selected, or None when removed.
    """

    file_changed = Signal(object)  # str | None

    def __init__(self, view: str, is_detail: bool = False, parent=None):
        super().__init__(parent)
        self.view = view
        self._path: str | None = None
        self._is_detail = is_detail
        self._build()
        self.setAcceptDrops(True)
        self._set_empty()

    # ── layout ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setObjectName("dropZone")
        self.setFixedHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._preview = QLabel(self)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setScaledContents(False)

        self._title = QLabel(self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not self._is_detail:
            icon = VIEW_ICONS.get(self.view, "")
            label = VIEW_LABELS.get(self.view, self.view.capitalize())
            self._title.setText(f"{icon}  {label}")
        else:
            self._title.setText(self.view)  # custom name for detail zones
        self._title.setStyleSheet("font-weight: 700; font-size: 12px; color: #374151;")

        self._hint = QLabel("Drop image here\nor click to browse")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("font-size: 11px; color: #9ca3af;")

        self._filename_lbl = QLabel("")
        self._filename_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._filename_lbl.setStyleSheet("font-size: 10px; color: #6b7280;")
        self._filename_lbl.setWordWrap(True)

        self._remove_btn = QPushButton("×")
        self._remove_btn.setObjectName("danger")
        self._remove_btn.setFixedSize(22, 22)
        self._remove_btn.setToolTip("Remove image")
        self._remove_btn.clicked.connect(self._remove_file)
        self._remove_btn.hide()

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self._title)
        top_row.addStretch()
        top_row.addWidget(self._remove_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        layout.addLayout(top_row)
        layout.addWidget(self._preview, stretch=1)
        layout.addWidget(self._hint)
        layout.addWidget(self._filename_lbl)

    def _set_empty(self) -> None:
        self.setStyleSheet(
            "ViewDropZone#dropZone {"
            "  border: 2px dashed #d1d5db;"
            "  border-radius: 8px;"
            "  background: #fafafa;"
            "}"
            "ViewDropZone#dropZone:hover {"
            "  border-color: #2563eb;"
            "  background: #eff6ff;"
            "}"
        )
        self._preview.setPixmap(QPixmap())
        self._preview.hide()
        self._hint.show()
        self._filename_lbl.hide()
        self._remove_btn.hide()

    def _set_loaded(self, path: str) -> None:
        self.setStyleSheet(
            "ViewDropZone#dropZone {"
            "  border: 2px solid #2563eb;"
            "  border-radius: 8px;"
            "  background: #eff6ff;"
            "}"
        )
        # Thumbnail
        pm = QPixmap(path)
        if not pm.isNull():
            pm = pm.scaled(
                self.width() - 24, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(pm)
            self._preview.show()
        self._hint.hide()
        self._filename_lbl.setText(Path(path).name)
        self._filename_lbl.show()
        self._remove_btn.show()

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def file_path(self) -> str | None:
        return self._path

    def set_file(self, path: str | None) -> None:
        self._path = path
        if path:
            self._set_loaded(path)
        else:
            self._set_empty()
        self.file_changed.emit(path)

    # ── interactions ─────────────────────────────────────────────────────────

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        self._browse()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select image — {self.view}",
            str(Path.cwd()),
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp)",
        )
        if path:
            self.set_file(path)

    def _remove_file(self) -> None:
        self.set_file(None)

    # ── drag & drop ──────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).suffix.lower() in _IMG_EXTS:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).suffix.lower() in _IMG_EXTS:
                self.set_file(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._path:
            self._set_loaded(self._path)
