"""About dialog: logo, program name/version, author link and licence text."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)

_RES = Path(__file__).parent.parent.parent / "res"
_LOGO_PATH = _RES / "logo.jpg"
_LICENCE_PATH = _RES / "LICENCE.txt"

_GITHUB_URL = "https://www.github.com/clem2k"


def _app_version() -> str:
    """Return the package version from installed metadata, with a fallback."""
    try:
        from importlib.metadata import version
        return version("paper2stl")
    except Exception:
        # Fallback: parse pyproject.toml if running from source.
        try:
            pyproject = _RES.parent.parent / "pyproject.toml"
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version") and "=" in stripped:
                    return stripped.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return "1.0.0"


class AboutDialog(QDialog):
    """Two halves: header (logo + identity) on top, licence text below."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("À propos de Paper2STL")
        self.setMinimumSize(640, 560)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top half: logo (left quarter) + identity (right) ────────────────
        header = QWidget()
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(header)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setSpacing(18)
        # left column ~1/4 of the width, right column ~3/4
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        if _LOGO_PATH.exists():
            pix = QPixmap(str(_LOGO_PATH))
            if not pix.isNull():
                logo.setPixmap(
                    pix.scaledToWidth(140, Qt.TransformationMode.SmoothTransformation)
                )
        grid.addWidget(logo, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        identity = QWidget()
        ident_lay = QVBoxLayout(identity)
        ident_lay.setContentsMargins(0, 0, 0, 0)
        ident_lay.setSpacing(6)
        ident_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(
            f"<span style='font-size:26px; font-weight:700; color:#111827;'>"
            f"PAPER2STL</span>"
            f"<span style='font-size:14px; color:#6b7280;'>"
            f" &nbsp;v{_app_version()}</span>"
        )
        ident_lay.addWidget(title)

        author = QLabel(
            "by clem2k<br>"
            f"<a href='{_GITHUB_URL}' style='color:#2563eb;'>{_GITHUB_URL}</a>"
        )
        author.setOpenExternalLinks(True)
        author.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        author.setStyleSheet("font-size:13px; color:#374151;")
        ident_lay.addWidget(author)

        grid.addWidget(identity, 0, 1, Qt.AlignmentFlag.AlignTop)
        root.addWidget(header, 1)

        # ── bottom half: licence text, full width, scrollable ───────────────
        licence = QTextEdit()
        licence.setReadOnly(True)
        licence.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        licence.setStyleSheet(
            "QTextEdit { border-top: 1px solid #e5e7eb; background:#fafafa; "
            "font-family: 'Consolas','Courier New',monospace; font-size:12px; "
            "color:#374151; padding:14px; }"
        )
        licence.setPlainText(self._licence_text())
        root.addWidget(licence, 1)

    @staticmethod
    def _licence_text() -> str:
        try:
            return _LICENCE_PATH.read_text(encoding="utf-8")
        except Exception:
            return "Licence file not found."
