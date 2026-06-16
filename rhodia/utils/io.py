"""Image and path I/O helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def read_image(path: str | Path) -> np.ndarray:
    """Read an image as BGR uint8, raising a clear error on failure."""
    path = Path(path)
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def list_images(folder: str | Path) -> list[Path]:
    """Return sorted image files in *folder* (non-recursive)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def save_debug(img: np.ndarray, path: str | Path) -> None:
    """Write an intermediate/debug image, creating parent dirs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
