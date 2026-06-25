"""Dialog to install the optional heavy modules (PyTorch, OCR) on demand."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from paper2stl.gui import extras


class ExtrasDialog(QDialog):
    """List each optional component with its status and a one-click installer.

    All installs run in a background thread and stream pip output into the log;
    the dialog refuses to close while an install is in progress.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modules optionnels")
        self.setMinimumSize(580, 560)
        self._worker: extras.InstallWorker | None = None
        self._status: dict[str, QLabel] = {}
        self._buttons: dict[str, QPushButton] = {}
        self._gpu_combo: QComboBox | None = None
        self._build()
        self._refresh_status()

    # ── construction ─────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        title = QLabel("<b style='font-size:16px;'>Modules optionnels</b>")
        root.addWidget(title)

        sub = QLabel(
            "Ces composants ne sont pas inclus par défaut (ils sont volumineux). "
            "Installez-les ici uniquement si vous en avez besoin — ils sont "
            "téléchargés dans l'environnement de l'application."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#6b7280; font-size:12px;")
        root.addWidget(sub)

        self._device_lbl = QLabel()
        self._device_lbl.setStyleSheet("color:#2563eb; font-size:12px;")
        root.addWidget(self._device_lbl)

        root.addWidget(_hline())

        # ── PyTorch row (with optional CUDA/CPU selector) ────────────────────
        gpu_row: QWidget | None = None
        if extras.gpu_choice_relevant():
            self._gpu_combo = QComboBox()
            self._gpu_combo.addItems(["GPU NVIDIA (CUDA)", "Processeur (CPU)"])
            gpu_row = QWidget()
            gl = QHBoxLayout(gpu_row)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.addWidget(QLabel("Variante :"))
            gl.addWidget(self._gpu_combo)
            gl.addStretch()

        torch_blurb = (
            "Accélération neurale : redressement des traits et complétion 3D "
            "(option <i>--neural-weights</i>). ~2 Go."
        )
        if extras.os_name() == "macos":
            torch_blurb += (" Utilisera le GPU Apple (MPS)."
                            if extras.is_apple_silicon() else " Utilisera le CPU.")
        root.addWidget(self._extra_row(
            "torch", "PyTorch", torch_blurb, extra_widget=gpu_row,
        ))

        # ── EasyOCR row ──────────────────────────────────────────────────────
        root.addWidget(self._extra_row(
            "easyocr", "OCR — EasyOCR",
            "Lit le cartouche pour nommer les vues automatiquement. "
            "Sans OCR, les vues sont reconnues par nom de fichier "
            "(front, top…). Installe PyTorch au passage. ~2 Go.",
        ))

        # ── Tesseract row ────────────────────────────────────────────────────
        root.addWidget(self._extra_row(
            "tesseract", "OCR — Tesseract",
            "Alternative légère à EasyOCR. Nécessite aussi le moteur système "
            "Tesseract (installé automatiquement via Homebrew sur macOS).",
        ))

        root.addWidget(_hline())

        # ── log ──────────────────────────────────────────────────────────────
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        self._log.setPlaceholderText("La sortie d'installation s'affichera ici…")
        self._log.setStyleSheet(
            "QPlainTextEdit { background:#1e1e2e; color:#cdd6f4;"
            " font-family:'Consolas','Fira Code',monospace; font-size:11px;"
            " border:none; border-radius:6px; padding:6px; }"
        )
        self._log.setMinimumHeight(150)
        root.addWidget(self._log, stretch=1)

        # ── footer ───────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        self._note = QLabel("")
        self._note.setStyleSheet("color:#6b7280; font-size:11px;")
        footer.addWidget(self._note, stretch=1)
        self._close_btn = QPushButton("Fermer")
        self._close_btn.clicked.connect(self.close)
        footer.addWidget(self._close_btn)
        root.addLayout(footer)

    def _extra_row(self, key: str, title: str, blurb: str,
                   extra_widget: QWidget | None = None) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background:#fff; border:1px solid #e5e7eb; border-radius:8px; }"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)
        name = QLabel(f"<b>{title}</b>")
        left.addWidget(name)
        desc = QLabel(blurb)
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#6b7280; font-size:11px;")
        left.addWidget(desc)
        if extra_widget is not None:
            left.addWidget(extra_widget)
        lay.addLayout(left, stretch=1)

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status = QLabel()
        status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._status[key] = status
        right.addWidget(status)
        btn = QPushButton("Installer")
        btn.setObjectName("primary")
        btn.clicked.connect(lambda _=False, k=key: self._install(k))
        self._buttons[key] = btn
        right.addWidget(btn)
        lay.addLayout(right)

        return frame

    # ── status ───────────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        states = {
            "torch": extras.module_installed("torch"),
            "easyocr": extras.module_installed("easyocr"),
            "tesseract": (extras.module_installed("pytesseract")
                          and extras.tesseract_binary_present()),
        }
        for key, ok in states.items():
            lbl = self._status[key]
            if ok:
                lbl.setText("✓ Installé")
                lbl.setStyleSheet("color:#16a34a; font-size:11px; font-weight:600;")
                self._buttons[key].setText("Réinstaller")
            else:
                lbl.setText("Non installé")
                lbl.setStyleSheet("color:#9ca3af; font-size:11px;")
                self._buttons[key].setText("Installer")

        try:
            from paper2stl.device import describe
            self._device_lbl.setText("Périphérique de calcul actuel : " + describe())
        except Exception:
            self._device_lbl.setText("")

    # ── install flow ─────────────────────────────────────────────────────────

    def _install(self, key: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        if key == "torch":
            use_cuda = (self._gpu_combo is None or self._gpu_combo.currentIndex() == 0)
            # On macOS there is no CUDA choice; use_cuda is ignored by the builder.
            commands, label = extras.torch_commands(use_cuda), "PyTorch"
        elif key == "easyocr":
            commands, label = extras.easyocr_commands(), "EasyOCR"
        elif key == "tesseract":
            commands, label = extras.tesseract_commands(), "Tesseract"
        else:
            return

        self._set_busy(True)
        self._note.setText(f"Installation de {label} en cours…")
        self._log.appendPlainText(f"\n=== Installation : {label} ===")

        self._worker = extras.InstallWorker(commands, label)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.done.connect(lambda ok, msg, k=key: self._on_done(ok, msg, k))
        self._worker.start()

    def _on_done(self, ok: bool, msg: str, key: str) -> None:
        self._log.appendPlainText(msg)

        if ok and key == "torch":
            # The device resolver is lru_cached; clear it so the freshly
            # installed backend is picked up without a restart.
            try:
                from paper2stl.device import get_device
                get_device.cache_clear()
            except Exception:
                pass

        if key == "tesseract" and not extras.tesseract_binary_present():
            hint = extras.tesseract_binary_hint()
            self._log.appendPlainText("⚠ " + hint)
            self._note.setText(hint)
        else:
            self._note.setText(
                msg + "  Redémarrez l'application pour une activation complète."
                if ok else msg
            )

        self._set_busy(False)
        self._refresh_status()

    def _set_busy(self, busy: bool) -> None:
        for btn in self._buttons.values():
            btn.setEnabled(not busy)
        self._close_btn.setEnabled(not busy)
        if self._gpu_combo is not None:
            self._gpu_combo.setEnabled(not busy)

    # ── guard against closing mid-install ────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._worker is not None and self._worker.isRunning():
            self._note.setText("Installation en cours — veuillez patienter…")
            event.ignore()
            return
        event.accept()


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color:#e5e7eb;")
    return line
