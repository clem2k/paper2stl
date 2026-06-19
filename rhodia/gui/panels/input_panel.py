"""Left panel: 6 face drop-zones + dynamic detail-zone list."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget, QGridLayout,
)

from rhodia.gui.widgets.drop_zone import ViewDropZone

_FACE_ORDER = ["front", "rear", "top", "bottom", "left", "right"]

# 2×3 grid layout
_GRID = [
    ("front", 0, 0), ("top",    0, 1), ("left",  0, 2),
    ("rear",  1, 0), ("bottom", 1, 1), ("right", 1, 2),
]


class DetailZoneRow(QWidget):
    """A single removable detail-zone row (label + drop zone + remove btn)."""

    removed = Signal(object)  # self

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self._index = index
        self._zone = ViewDropZone(f"Detail {index}", is_detail=True)
        remove_btn = QPushButton("× Remove")
        remove_btn.setObjectName("danger")
        remove_btn.setFixedWidth(80)
        remove_btn.setFixedHeight(28)
        remove_btn.setStyleSheet(
            "QPushButton { border: 1px solid #fca5a5; border-radius: 4px; "
            "color: #dc2626; background: #fff1f2; font-size: 11px; } "
            "QPushButton:hover { background: #fecaca; }"
        )
        remove_btn.clicked.connect(lambda: self.removed.emit(self))

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(self._zone, stretch=1)
        h.addWidget(remove_btn, alignment=Qt.AlignmentFlag.AlignTop)

    @property
    def file_path(self) -> str | None:
        return self._zone.file_path


class InputPanel(QWidget):
    """The left panel containing face drop-zones and detail zones.

    Signals
    -------
    views_changed : dict[str, str | None]
        Emitted whenever any face image changes; maps view name → path | None.
    details_changed : list[str]
        Emitted whenever the detail-zone file list changes; list of non-None paths.
    """

    views_changed   = Signal(dict)
    details_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zones:  dict[str, ViewDropZone] = {}
        self._detail_rows: list[DetailZoneRow] = []
        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        inner = QWidget()
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(16)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        # ── views grid ────────────────────────────────────────────────────────
        sec_lbl = QLabel("Orthographic Views")
        sec_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #6b7280; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        self._layout.addWidget(sec_lbl)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for name, row, col in _GRID:
            zone = ViewDropZone(name)
            zone.file_changed.connect(lambda _, n=name: self._on_view_changed(n))
            grid.addWidget(zone, row, col)
            self._zones[name] = zone
        self._layout.addWidget(grid_widget)

        # ── detail zones ──────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e5e7eb;")
        self._layout.addWidget(sep)

        detail_hdr = QHBoxLayout()
        detail_lbl = QLabel("Detail Zones")
        detail_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #6b7280; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        detail_hint = QLabel(
            "Scans identified by a red cartouche that zoom into a sub-region of a face."
        )
        detail_hint.setStyleSheet("font-size: 11px; color: #9ca3af;")
        detail_hint.setWordWrap(True)
        detail_hdr.addWidget(detail_lbl)
        self._layout.addLayout(detail_hdr)
        self._layout.addWidget(detail_hint)

        self._details_container = QVBoxLayout()
        self._details_container.setSpacing(6)
        self._layout.addLayout(self._details_container)

        add_btn = QPushButton("+ Add detail zone")
        add_btn.setObjectName("ghost")
        add_btn.setFixedHeight(36)
        add_btn.clicked.connect(self._add_detail)
        self._layout.addWidget(add_btn)
        self._layout.addStretch()

    # ── detail zones management ───────────────────────────────────────────────

    def _add_detail(self) -> None:
        idx = len(self._detail_rows) + 1
        row = DetailZoneRow(idx, self)
        row.removed.connect(self._remove_detail)
        row._zone.file_changed.connect(lambda _: self._on_details_changed())
        self._details_container.addWidget(row)
        self._detail_rows.append(row)

    def _remove_detail(self, row: DetailZoneRow) -> None:
        self._details_container.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._detail_rows.remove(row)
        self._on_details_changed()

    # ── signals ───────────────────────────────────────────────────────────────

    def _on_view_changed(self, _name: str) -> None:
        self.views_changed.emit(self.get_view_paths())

    def _on_details_changed(self) -> None:
        self.details_changed.emit(self.get_detail_paths())

    # ── public API ────────────────────────────────────────────────────────────

    def get_view_paths(self) -> dict[str, str | None]:
        return {name: zone.file_path for name, zone in self._zones.items()}

    def get_detail_paths(self) -> list[str]:
        return [r.file_path for r in self._detail_rows if r.file_path]

    def has_any_input(self) -> bool:
        return any(z.file_path for z in self._zones.values())
