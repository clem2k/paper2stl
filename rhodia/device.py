"""Dynamic hardware acceleration selection.

Resolves the best available compute device for any deep-learning component
(line straightening, OCR, neural 3D completion):

    CUDA  (Nvidia GPU)  >  MPS  (Apple Silicon unified memory)  >  CPU

The resolver is intentionally torch-optional: if torch is not installed the
pipeline still runs its deterministic (numpy/OpenCV) core, and ``get_device``
simply returns the string ``"cpu"``.
"""

from __future__ import annotations

import functools
import logging

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def get_device(prefer: str | None = None) -> str:
    """Return the best available device identifier as a string.

    Parameters
    ----------
    prefer:
        Force a specific backend (``"cuda"``, ``"mps"``, ``"cpu"``).  If the
        requested backend is unavailable the function logs a warning and falls
        back through the normal priority chain.

    Returns
    -------
    str
        One of ``"cuda"``, ``"mps"`` or ``"cpu"``.  Returned as a string so
        that callers without torch can still branch on it.
    """
    try:
        import torch
    except ImportError:
        if prefer and prefer != "cpu":
            logger.warning("torch not installed; '%s' unavailable, using cpu", prefer)
        return "cpu"

    available = {"cpu": True}
    available["cuda"] = bool(torch.cuda.is_available())
    # MPS is exposed under torch.backends.mps on Apple Silicon builds.
    available["mps"] = bool(
        getattr(torch.backends, "mps", None)
        and torch.backends.mps.is_available()
        and torch.backends.mps.is_built()
    )

    if prefer:
        if available.get(prefer):
            logger.info("Using requested device: %s", prefer)
            return prefer
        logger.warning("Requested device '%s' unavailable; auto-selecting", prefer)

    for candidate in ("cuda", "mps", "cpu"):
        if available.get(candidate):
            logger.info("Selected compute device: %s", candidate)
            return candidate
    return "cpu"


def torch_device(prefer: str | None = None):
    """Return an actual ``torch.device`` (imports torch lazily)."""
    import torch

    return torch.device(get_device(prefer))


def describe() -> str:
    """Human-readable one-line summary of the resolved acceleration."""
    dev = get_device()
    detail = {
        "cuda": "Nvidia CUDA GPU",
        "mps": "Apple Silicon GPU (Metal / unified memory)",
        "cpu": "CPU (no hardware accelerator detected)",
    }[dev]
    return f"compute device = {dev} ({detail})"
