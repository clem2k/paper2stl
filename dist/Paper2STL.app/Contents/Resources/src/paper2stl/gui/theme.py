"""Application theme: palette + stylesheet."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# ── Colour tokens ──────────────────────────────────────────────────────────────
BG        = "#f0f2f5"
BG_CARD   = "#ffffff"
BG_DARK   = "#e4e7ec"
BORDER    = "#d1d5db"
ACCENT    = "#2563eb"
ACCENT_HV = "#1d4ed8"
TEXT      = "#111827"
TEXT_MUT  = "#6b7280"
SUCCESS   = "#16a34a"
WARN      = "#d97706"
ERROR     = "#dc2626"
RADIUS    = "8px"
RADIUS_SM = "4px"


STYLESHEET = f"""
/* ── global ───────────────────────────────────────────────────────────────── */
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

/* ── scroll areas ──────────────────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    width: 8px;
    background: {BG_DARK};
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #9ca3af;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    height: 8px;
    background: {BG_DARK};
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #9ca3af;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── splitter ──────────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BORDER};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── group box (collapsible section) ────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS};
    margin-top: 18px;
    padding: 8px 10px;
    background: {BG_CARD};
    font-weight: 600;
    font-size: 12px;
    color: {TEXT_MUT};
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}}

/* ── form labels ───────────────────────────────────────────────────────────── */
QLabel.param-label {{
    color: {TEXT};
    font-size: 12px;
}}
QLabel.muted {{
    color: {TEXT_MUT};
    font-size: 11px;
}}

/* ── line edits ──────────────────────────────────────────────────────────────*/
QLineEdit, QPlainTextEdit {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 5px 8px;
    background: {BG_CARD};
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
    outline: none;
}}

/* ── spin boxes ──────────────────────────────────────────────────────────────*/
QSpinBox, QDoubleSpinBox {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 3px 6px;
    background: {BG_CARD};
    min-width: 72px;
    max-width: 88px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 16px;
    border: none;
    background: {BG_DARK};
    border-radius: 2px;
}}

/* ── sliders ─────────────────────────────────────────────────────────────────*/
QSlider::groove:horizontal {{
    height: 4px;
    background: {BG_DARK};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    border-radius: 7px;
    background: {ACCENT};
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── check boxes ─────────────────────────────────────────────────────────────*/
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: {RADIUS_SM};
    border: 1.5px solid {BORDER};
    background: {BG_CARD};
}}
QCheckBox::indicator:checked {{
    border-color: {ACCENT};
    background: {ACCENT};
}}

/* ── combo boxes ─────────────────────────────────────────────────────────────*/
QComboBox {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 5px 10px;
    background: {BG_CARD};
    min-width: 100px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    border-radius: {RADIUS_SM};
}}

/* ── push buttons ────────────────────────────────────────────────────────────*/
QPushButton {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SM};
    padding: 6px 14px;
    background: {BG_CARD};
    color: {TEXT};
    font-weight: 500;
}}
QPushButton:hover  {{ background: {BG_DARK}; }}
QPushButton:pressed {{ background: #d1d5db; }}

QPushButton#primary {{
    background: {ACCENT};
    color: #fff;
    border-color: {ACCENT};
    font-weight: 600;
    font-size: 14px;
    padding: 8px 28px;
    border-radius: 6px;
}}
QPushButton#primary:hover  {{ background: {ACCENT_HV}; border-color: {ACCENT_HV}; }}
QPushButton#primary:disabled {{ background: #93c5fd; border-color: #93c5fd; }}

QPushButton#danger {{
    background: transparent;
    color: {ERROR};
    border: none;
    padding: 2px 6px;
    font-size: 16px;
    font-weight: 700;
}}
QPushButton#danger:hover {{ color: #b91c1c; }}

QPushButton#ghost {{
    background: transparent;
    border: 1px dashed {BORDER};
    color: {TEXT_MUT};
    font-size: 12px;
}}
QPushButton#ghost:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}

/* ── progress bar ────────────────────────────────────────────────────────────*/
QProgressBar {{
    border: none;
    background: {BG_DARK};
    border-radius: {RADIUS_SM};
    height: 6px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: {RADIUS_SM};
}}

/* ── tool bar ────────────────────────────────────────────────────────────────*/
QToolBar {{
    background: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    padding: 6px 12px;
    spacing: 8px;
}}

/* ── tab bar (not used yet, but available) ──────────────────────────────────*/
QTabBar::tab {{
    padding: 6px 14px;
    border-bottom: 2px solid transparent;
    color: {TEXT_MUT};
}}
QTabBar::tab:selected {{
    border-bottom-color: {ACCENT};
    color: {TEXT};
    font-weight: 600;
}}

/* ── status bar ──────────────────────────────────────────────────────────────*/
QStatusBar {{
    background: {BG_CARD};
    border-top: 1px solid {BORDER};
    font-size: 12px;
    color: {TEXT_MUT};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Base,            QColor(BG_CARD))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_DARK))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Button,          QColor(BG_CARD))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Text,            QColor(TEXT))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    app.setPalette(pal)
