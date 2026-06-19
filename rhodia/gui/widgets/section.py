"""Collapsible section widget (animates open/close)."""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


class CollapsibleSection(QWidget):
    """A titled group that can be expanded or collapsed.

    Usage
    -----
    sec = CollapsibleSection("Grid Removal")
    sec.add_widget(FloatRow(...))
    """

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._build(title)

    def _build(self, title: str) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 4)
        outer.setSpacing(0)

        # ── header ──────────────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            "QFrame {"
            "  background: #f3f4f6;"
            "  border: 1px solid #e5e7eb;"
            "  border-radius: 6px;"
            "}"
        )
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header.setFixedHeight(32)
        header.mousePressEvent = lambda _: self.toggle()

        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setSpacing(6)

        self._arrow = QLabel("▾" if self._expanded else "▸")
        self._arrow.setStyleSheet("font-size: 11px; color: #6b7280; font-weight: 700;")
        self._arrow.setFixedWidth(14)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #4b5563; letter-spacing: 0.4px;"
        )

        h_layout.addWidget(self._arrow)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        outer.addWidget(header)

        # ── content ──────────────────────────────────────────────────────────
        self._content = QFrame()
        self._content.setStyleSheet(
            "QFrame {"
            "  background: #ffffff;"
            "  border: 1px solid #e5e7eb;"
            "  border-top: none;"
            "  border-bottom-left-radius: 6px;"
            "  border-bottom-right-radius: 6px;"
            "}"
        )
        self._inner = QVBoxLayout(self._content)
        self._inner.setContentsMargins(12, 8, 12, 10)
        self._inner.setSpacing(4)
        outer.addWidget(self._content)

        if not self._expanded:
            self._content.hide()

    # ── public API ────────────────────────────────────────────────────────────

    def add_widget(self, w: QWidget) -> None:
        self._inner.addWidget(w)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._arrow.setText("▾" if self._expanded else "▸")
        self._content.setVisible(self._expanded)

    def set_expanded(self, v: bool) -> None:
        if v != self._expanded:
            self.toggle()
