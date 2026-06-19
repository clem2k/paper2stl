"""OCR wrapper + orthographic view classification from the cartouche.

The view keyword (top/front/bottom/rear/left/right) is written in the upper
right cartouche.  We crop that region, OCR it, and fuzzy-match against the
canonical view vocabulary (English + common French synonyms).
"""

from __future__ import annotations

import difflib
import logging

import numpy as np

from ..config import MetadataConfig
from ..device import get_device

logger = logging.getLogger(__name__)

# Canonical views and accepted spellings (lowercased).
VIEW_VOCAB: dict[str, list[str]] = {
    "top": ["top", "dessus", "haut", "plan"],
    "bottom": ["bottom", "dessous", "bas"],
    "front": ["front", "face", "avant"],
    "rear": ["rear", "back", "arriere", "arrière", "dos"],
    "left": ["left", "gauche"],
    "right": ["right", "droite", "droit"],
}
_FLAT_VOCAB = {alias: canon for canon, aliases in VIEW_VOCAB.items() for alias in aliases}


class OCREngine:
    """Lazy, backend-agnostic OCR engine (EasyOCR or Tesseract)."""

    def __init__(self, backend: str = "auto", device: str | None = None):
        self.requested = backend
        self.device = device or get_device()
        self._reader = None
        self.backend = None

    def _ensure(self) -> None:
        if self._reader is not None or self.backend == "none":
            return
        order = (
            ["easyocr", "tesseract"]
            if self.requested == "auto"
            else [self.requested]
        )
        for backend in order:
            try:
                if backend == "easyocr":
                    import easyocr

                    gpu = self.device in ("cuda", "mps")
                    self._reader = easyocr.Reader(["en", "fr"], gpu=gpu)
                    self.backend = "easyocr"
                    return
                if backend == "tesseract":
                    import pytesseract  # noqa: F401

                    self._reader = pytesseract
                    self.backend = "tesseract"
                    return
            except Exception as exc:  # pragma: no cover - env dependent
                logger.warning("OCR backend '%s' unavailable: %s", backend, exc)
        self.backend = "none"
        logger.warning("No OCR backend available; metadata text will be empty")

    def read_text(self, image: np.ndarray) -> str:
        """Return concatenated recognised text (lowercased)."""
        self._ensure()
        if self.backend == "none":
            return ""
        if self.backend == "easyocr":
            results = self._reader.readtext(image, detail=0)
            return " ".join(results).lower()
        # tesseract
        return self._reader.image_to_string(image).strip().lower()


def _crop_cartouche(image: np.ndarray, cfg: MetadataConfig) -> np.ndarray:
    h, w = image.shape[:2]
    x0 = int(w * cfg.cartouche_frac[0])
    y1 = int(h * cfg.cartouche_frac[1])
    return image[0:y1, x0:w]


def match_view(text: str) -> tuple[str | None, float]:
    """Fuzzy-match a free-text string against the view vocabulary.

    Returns ``(view_name | None, confidence)`` with confidence in [0, 1].
    Tolerant of OCR noise (uses ratio matching on each alphabetic token).
    """
    if not text:
        return None, 0.0
    best_view, best_score = None, 0.0
    for token in text.replace("\n", " ").replace("_", " ").replace("-", " ").split():
        token = "".join(ch for ch in token if ch.isalpha()).lower()
        if not token:
            continue
        match = difflib.get_close_matches(token, _FLAT_VOCAB.keys(), n=1, cutoff=0.7)
        if match:
            score = difflib.SequenceMatcher(None, token, match[0]).ratio()
            if score > best_score:
                best_view, best_score = _FLAT_VOCAB[match[0]], score
    return best_view, float(best_score)


def classify_view(
    image: np.ndarray,
    engine: OCREngine | None = None,
    cfg: MetadataConfig | None = None,
) -> tuple[str | None, float]:
    """Classify the orthographic view from the cartouche.

    Returns ``(view_name | None, confidence)`` where confidence is in [0, 1].
    """
    cfg = cfg or MetadataConfig()
    engine = engine or OCREngine(cfg.ocr_backend)
    crop = _crop_cartouche(image, cfg)
    text = engine.read_text(crop)
    return match_view(text)
