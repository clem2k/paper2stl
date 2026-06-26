"""Paper2STL graphical user interface (PySide6)."""

from __future__ import annotations

from pathlib import Path

_RES = Path(__file__).parent.parent / "res"
_ICON_PATH = _RES / "ico.ico" if (_RES / "ico.ico").exists() else _RES / "ico.png"


def run_gui() -> int:
    """Launch the GUI and return its exit code."""
    import sys
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from .windows.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Paper2STL")
    app.setOrganizationName("Paper2STL")

    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    from .theme import apply_theme
    apply_theme(app)

    win = MainWindow()
    win.show()
    return app.exec()
