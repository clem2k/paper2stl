"""On-demand installation of the heavy optional components (PyTorch, OCR).

These extras are deliberately *not* bundled in the lightweight Mac app — they
are downloaded on demand from the GUI (``Modules`` menu). Every install targets
the **current interpreter's** environment via ``sys.executable -m pip`` so the
packages land in exactly the venv the app is running from (the one created at
``~/Library/Application Support/Paper2STL/venv`` for the bundled app, or the
developer's venv when run from source).

The pip command is chosen per OS / GPU:

* **PyTorch**
    - macOS        → default PyPI wheel (MPS on Apple Silicon, CPU on Intel).
    - Windows+CUDA → pinned ``+cu121`` wheels from the PyTorch CUDA index.
    - Windows CPU  → CPU index.
    - Linux+CUDA   → default PyPI wheel (already bundles CUDA on Linux).
    - Linux CPU    → CPU index.
* **EasyOCR**   → ``pip install easyocr`` (same everywhere; pulls torch).
* **Tesseract** → ``pip install pytesseract`` + the system binary
    (``brew install tesseract`` on macOS; manual on Linux/Windows — we never
    run ``sudo`` from the GUI).
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys

from PySide6.QtCore import QThread, Signal

# Base pip invocation (non-interactive so it can never block on a prompt).
_PIP = [sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check", "--no-input"]

# PyTorch CUDA pins (see https://pytorch.org/get-started/locally/ for newer series).
_CUDA_INDEX = "https://download.pytorch.org/whl/cu121"
_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
_TORCH_CUDA = ["torch==2.5.1+cu121", "torchvision==0.20.1+cu121"]


# ── platform / install-state detection ──────────────────────────────────────

def os_name() -> str:
    """``"macos"`` | ``"windows"`` | ``"linux"`` (or the lowercased system)."""
    return {"Darwin": "macos", "Windows": "windows",
            "Linux": "linux"}.get(platform.system(), platform.system().lower())


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def has_nvidia_gpu() -> bool:
    """True if an Nvidia GPU is usable (``nvidia-smi`` present and runnable)."""
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, timeout=5, check=True)
        return True
    except Exception:
        return False


def gpu_choice_relevant() -> bool:
    """Whether to offer a CUDA-vs-CPU choice (only on Windows/Linux + Nvidia)."""
    return os_name() in ("windows", "linux") and has_nvidia_gpu()


def module_installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def tesseract_binary_present() -> bool:
    return shutil.which("tesseract") is not None


# ── pip command builders ────────────────────────────────────────────────────

def torch_commands(use_cuda: bool) -> list[list[str]]:
    o = os_name()
    if o == "macos":
        # Default wheel already supports MPS (Apple Silicon) / CPU (Intel).
        return [_PIP + ["torch", "torchvision"]]
    if o == "windows":
        if use_cuda:
            return [_PIP + _TORCH_CUDA + ["--index-url", _CUDA_INDEX]]
        return [_PIP + ["torch", "torchvision", "--index-url", _CPU_INDEX]]
    # linux
    if use_cuda:
        return [_PIP + ["torch", "torchvision"]]      # PyPI bundles CUDA on Linux
    return [_PIP + ["torch", "torchvision", "--index-url", _CPU_INDEX]]


def easyocr_commands() -> list[list[str]]:
    # EasyOCR pulls torch automatically if it is not present yet.
    return [_PIP + ["easyocr"]]


def tesseract_commands() -> list[list[str]]:
    cmds = [_PIP + ["pytesseract"]]
    # The Python wrapper needs the native engine. brew needs no sudo → safe to
    # run; apt/Windows need elevation or a manual installer, so we only advise.
    if os_name() == "macos" and shutil.which("brew"):
        cmds.append(["brew", "install", "tesseract"])
    return cmds


def tesseract_binary_hint() -> str:
    """OS-specific instruction for the native Tesseract engine."""
    o = os_name()
    if o == "macos":
        return ("Moteur Tesseract manquant — installez Homebrew (https://brew.sh) "
                "puis exécutez :  brew install tesseract")
    if o == "linux":
        return ("Moteur Tesseract manquant — installez-le via votre gestionnaire "
                "de paquets, par ex. :  sudo apt install tesseract-ocr")
    if o == "windows":
        return ("Moteur Tesseract manquant — installez le binaire Windows depuis "
                "https://github.com/UB-Mannheim/tesseract/wiki")
    return "Moteur Tesseract manquant — installez le binaire pour votre système."


# ── background installer ─────────────────────────────────────────────────────

class InstallWorker(QThread):
    """Run a sequence of install commands, streaming their output line by line.

    Signals
    -------
    line : str   one line of combined stdout/stderr.
    done : (bool, str)   success flag + human message, emitted once at the end.
    """

    line = Signal(str)
    done = Signal(bool, str)

    def __init__(self, commands: list[list[str]], label: str):
        super().__init__()
        self._commands = commands
        self._label = label

    def run(self) -> None:  # noqa: D401 - QThread entry point
        creation: dict = {}
        if os_name() == "windows":
            creation["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        for cmd in self._commands:
            self.line.emit("→ " + " ".join(cmd))
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, **creation,
                )
            except FileNotFoundError as exc:
                self.done.emit(False, f"Commande introuvable : {cmd[0]} ({exc})")
                return

            if proc.stdout is not None:
                for raw in proc.stdout:
                    self.line.emit(raw.rstrip("\n"))
            proc.wait()
            if proc.returncode != 0:
                self.done.emit(
                    False, f"« {self._label} » a échoué (code {proc.returncode})."
                )
                return

        self.done.emit(True, f"« {self._label} » installé avec succès.")
