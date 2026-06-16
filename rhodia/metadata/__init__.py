"""Stage B — metadata extraction: view classification + red detail frames."""

from .ocr import classify_view, OCREngine
from .red_frames import detect_red_frames, DetailReference

__all__ = ["classify_view", "OCREngine", "detect_red_frames", "DetailReference"]
