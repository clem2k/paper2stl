"""Scrolling log view with colour coding by level."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

_LEVEL_COLORS = {
    "DEBUG":   "#FFFFFF",
    "INFO":    "#FFFFFF",
    "WARNING": "#FFFF00",
    "ERROR":   "#FF9900",
    "CRITICAL":"#FF0000",
}


class LogView(QWidget):
    """Collapsible log panel with clear button and colour-coded levels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet("background:#f3f4f6; border-top: 1px solid #e5e7eb;")
        h = QHBoxLayout(header)
        h.setContentsMargins(12, 4, 12, 4)
        lbl = QLabel("Log")
        lbl.setStyleSheet("font-weight: 700; font-size: 11px; color: #6b7280;")
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(52)
        clear_btn.setStyleSheet(
            "QPushButton { border: none; color: #6b7280; font-size: 11px; "
            "background: transparent; } "
            "QPushButton:hover { color: #2563eb; }"
        )
        clear_btn.clicked.connect(self.clear)
        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(clear_btn)
        layout.addWidget(header)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(2000)
        self._text.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #1e1e2e;"
            "  color: #cdd6f4;"
            "  font-family: 'Consolas', 'Fira Code', monospace;"
            "  font-size: 11px;"
            "  border: none;"
            "}"
        )
        self._text.setMinimumHeight(90)
        self._text.setMaximumHeight(200)
        layout.addWidget(self._text)

    @Slot(str)
    def append(self, line: str) -> None:
        level = "INFO"
        for lvl in _LEVEL_COLORS:
            if line.startswith(lvl) or f" {lvl} " in line:
                level = lvl
                break
        color = _LEVEL_COLORS.get(level, "#cdd6f4")

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cur = self._text.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.insertText(line + "\n", fmt)
        self._text.setTextCursor(cur)
        self._text.ensureCursorVisible()

    def clear(self) -> None:
        self._text.clear()
