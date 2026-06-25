"""Paper2STL graphical user interface (PySide6)."""

from __future__ import annotations


def run_gui() -> int:
    """Launch the GUI and return its exit code."""
    import sys
    from PySide6.QtWidgets import QApplication
    from .windows.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Paper2STL")
    app.setOrganizationName("Paper2STL")

    from .theme import apply_theme
    apply_theme(app)

    win = MainWindow()
    win.show()
    return app.exec()
