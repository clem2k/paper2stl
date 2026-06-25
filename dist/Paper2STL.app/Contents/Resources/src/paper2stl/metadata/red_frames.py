"""Detect red detail-reference frames and OCR the reference inside them."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..config import MetadataConfig
from .ocr import OCREngine


@dataclass
class DetailReference:
    """A red-boxed reference pointing to another (detail) scan."""

    bbox: tuple[int, int, int, int]   # x, y, w, h in pixels
    text: str                          # OCR'd reference, e.g. "DET-A3"
    center_norm: tuple[float, float]   # box centre, normalised to [0,1] in image


def _red_mask(bgr: np.ndarray, cfg: MetadataConfig) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in cfg.red_hue_ranges:
        lower = np.array([lo, cfg.red_min_saturation, cfg.red_min_value])
        upper = np.array([hi, 255, 255])
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return mask


def detect_red_frames(
    bgr: np.ndarray,
    engine: OCREngine | None = None,
    cfg: MetadataConfig | None = None,
) -> list[DetailReference]:
    """Find rectangular red frames and read the reference text inside each."""
    cfg = cfg or MetadataConfig()
    engine = engine or OCREngine(cfg.ocr_backend)
    h, w = bgr.shape[:2]
    min_area = cfg.red_min_box_area_frac * h * w

    mask = _red_mask(bgr, cfg)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    refs: list[DetailReference] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
        # Accept quadrilateral-ish frames (4–6 corners after simplification).
        if not (4 <= len(approx) <= 6):
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        # OCR the interior (inset to avoid reading the red border itself).
        inset = max(2, int(0.05 * min(bw, bh)))
        roi = bgr[y + inset : y + bh - inset, x + inset : x + bw - inset]
        text = engine.read_text(roi) if roi.size else ""
        refs.append(
            DetailReference(
                bbox=(x, y, bw, bh),
                text=text.strip(),
                center_norm=((x + bw / 2) / w, (y + bh / 2) / h),
            )
        )
    return refs
