"""Compact parameter widgets: slider+spinbox, checkbox, combobox, path picker."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget,
)


class _BaseRow(QWidget):
    """Base: label + description tooltip + value widget in one row."""

    def __init__(self, label: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self._lbl = QLabel(label)
        self._lbl.setFixedWidth(178)
        self._lbl.setWordWrap(False)
        self._lbl.setStyleSheet("font-size: 12px; color: #374151;")
        if tooltip:
            self._lbl.setToolTip(tooltip)
            self.setToolTip(tooltip)

    def _make_row(self, value_widget: QWidget) -> None:
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(10)
        h.addWidget(self._lbl)
        h.addWidget(value_widget, stretch=1)


# ── Float slider + spinbox ──────────────────────────────────────────────────────

class FloatRow(_BaseRow):
    """Label + QSlider (continuous) + QDoubleSpinBox, kept in sync."""

    value_changed = Signal(float)

    def __init__(
        self,
        label: str,
        minimum: float,
        maximum: float,
        step: float = 0.01,
        default: float = 0.0,
        decimals: int = 2,
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(label, tooltip, parent)
        self._min = minimum
        self._max = maximum
        self._step = step
        self._scale = round(1.0 / step) if step > 0 else 100

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(int(minimum * self._scale), int(maximum * self._scale))
        self._slider.setSingleStep(1)
        self._slider.setPageStep(max(1, int(self._scale * 0.1 * (maximum - minimum))))

        self._spin = QDoubleSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        self._spin.setFixedWidth(80)

        self._slider.valueChanged.connect(self._from_slider)
        self._spin.valueChanged.connect(self._from_spin)
        self.set_value(default)

        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(self._slider, stretch=1)
        h.addWidget(self._spin)
        self._make_row(container)

    def _from_slider(self, v: int) -> None:
        val = v / self._scale
        self._spin.blockSignals(True)
        self._spin.setValue(val)
        self._spin.blockSignals(False)
        self.value_changed.emit(val)

    def _from_spin(self, v: float) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(int(v * self._scale))
        self._slider.blockSignals(False)
        self.value_changed.emit(v)

    def get_value(self) -> float:
        return self._spin.value()

    def set_value(self, v: float) -> None:
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(float(v))
        self._slider.setValue(int(float(v) * self._scale))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)


# ── Int slider + spinbox ────────────────────────────────────────────────────────

class IntRow(_BaseRow):
    """Label + QSlider (integer) + QSpinBox, kept in sync."""

    value_changed = Signal(int)

    def __init__(
        self,
        label: str,
        minimum: int,
        maximum: int,
        step: int = 1,
        default: int = 0,
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(label, tooltip, parent)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setSingleStep(step)

        self._spin = QSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setSingleStep(step)
        self._spin.setFixedWidth(80)

        self._slider.valueChanged.connect(self._from_slider)
        self._spin.valueChanged.connect(self._from_spin)
        self.set_value(default)

        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(self._slider, stretch=1)
        h.addWidget(self._spin)
        self._make_row(container)

    def _from_slider(self, v: int) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)
        self.value_changed.emit(v)

    def _from_spin(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)
        self.value_changed.emit(v)

    def get_value(self) -> int:
        return self._spin.value()

    def set_value(self, v: int) -> None:
        self._spin.blockSignals(True)
        self._slider.blockSignals(True)
        self._spin.setValue(int(v))
        self._slider.setValue(int(v))
        self._spin.blockSignals(False)
        self._slider.blockSignals(False)


# ── Optional numeric (None = disabled) ─────────────────────────────────────────

class OptionalFloatRow(_BaseRow):
    """Checkbox + float spinbox; disabled state represents None."""

    value_changed = Signal(object)  # float | None

    def __init__(
        self,
        label: str,
        minimum: float,
        maximum: float,
        step: float = 1.0,
        default: float | None = None,
        unit: str = "",
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(label, tooltip, parent)
        self._cb = QCheckBox()
        self._spin = QDoubleSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(1)
        self._spin.setFixedWidth(88)
        if unit:
            self._spin.setSuffix(f" {unit}")
        self._spin.setEnabled(False)

        self._cb.toggled.connect(self._on_toggle)
        self._spin.valueChanged.connect(lambda _: self.value_changed.emit(self.get_value()))

        if default is not None:
            self._cb.setChecked(True)
            self._spin.setValue(default)
        else:
            self._cb.setChecked(False)
            self._spin.setValue(minimum)

        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(self._cb)
        h.addWidget(self._spin)
        h.addStretch()
        self._make_row(container)

    def _on_toggle(self, checked: bool) -> None:
        self._spin.setEnabled(checked)
        self.value_changed.emit(self.get_value())

    def get_value(self) -> float | None:
        return self._spin.value() if self._cb.isChecked() else None

    def set_value(self, v: float | None) -> None:
        if v is None:
            self._cb.setChecked(False)
            self._spin.setEnabled(False)
        else:
            self._cb.setChecked(True)
            self._spin.setEnabled(True)
            self._spin.setValue(v)


# ── Bool checkbox ───────────────────────────────────────────────────────────────

class BoolRow(_BaseRow):
    """Label + QCheckBox."""

    value_changed = Signal(bool)

    def __init__(self, label: str, default: bool = True, tooltip: str = "", parent=None):
        super().__init__(label, tooltip, parent)
        self._cb = QCheckBox()
        self._cb.setChecked(default)
        self._cb.toggled.connect(self.value_changed.emit)
        self._make_row(self._cb)

    def get_value(self) -> bool:
        return self._cb.isChecked()

    def set_value(self, v: bool) -> None:
        self._cb.setChecked(v)


# ── Enum / choice ───────────────────────────────────────────────────────────────

class ChoiceRow(_BaseRow):
    """Label + QComboBox for string choices."""

    value_changed = Signal(str)

    def __init__(
        self,
        label: str,
        choices: list[str],
        default: str = "",
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(label, tooltip, parent)
        self._combo = QComboBox()
        self._combo.addItems(choices)
        idx = choices.index(default) if default in choices else 0
        self._combo.setCurrentIndex(idx)
        self._combo.currentTextChanged.connect(self.value_changed.emit)
        self._make_row(self._combo)

    def get_value(self) -> str:
        return self._combo.currentText()

    def set_value(self, v: str) -> None:
        idx = self._combo.findText(v)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)


# ── Path picker ─────────────────────────────────────────────────────────────────

class OptionalPathRow(_BaseRow):
    """Checkbox + path line-edit + folder-browse button.  None when disabled."""

    value_changed = Signal(object)  # str | None

    def __init__(
        self,
        label: str,
        default: str | None = None,
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(label, tooltip, parent)
        self._cb = QCheckBox()
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Select folder…")
        self._edit.setEnabled(False)
        self._browse = QPushButton("…")
        self._browse.setFixedWidth(28)
        self._browse.setEnabled(False)
        self._browse.clicked.connect(self._pick)
        self._cb.toggled.connect(self._on_toggle)
        self._edit.textChanged.connect(lambda _: self.value_changed.emit(self.get_value()))

        if default:
            self._cb.setChecked(True)
            self._edit.setText(default)

        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(self._cb)
        h.addWidget(self._edit, stretch=1)
        h.addWidget(self._browse)
        self._make_row(container)

    def _on_toggle(self, checked: bool) -> None:
        self._edit.setEnabled(checked)
        self._browse.setEnabled(checked)
        self.value_changed.emit(self.get_value())

    def _pick(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select folder")
        if d:
            self._edit.setText(d)

    def get_value(self) -> str | None:
        return self._edit.text().strip() or None if self._cb.isChecked() else None

    def set_value(self, v: str | None) -> None:
        if v:
            self._cb.setChecked(True)
            self._edit.setText(v)
        else:
            self._cb.setChecked(False)
            self._edit.clear()
