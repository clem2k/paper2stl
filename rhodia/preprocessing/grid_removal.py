"""Remove the Rhodia quadrille (light blue/violet grid) from a scan.

Two complementary cues are exploited:

1. **Colour** — the printed grid is chromatic (blue/violet) while pencil is
   near-neutral grey/black.  In HSV we mask out chromatic pixels in the grid
   hue band and inpaint them from neighbouring (achromatic) pixels.
2. **Frequency** — the grid is a periodic high-frequency pattern.  An optional
   FFT notch pass can suppress residual periodic lines.  It is disabled by
   default because the colour route is both faster and more robust on real
   scans, but it is available for greyscale-only scans.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import PreprocessConfig


def _grid_color_mask(bgr: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    """Binary mask (uint8 0/255) of chromatic grid pixels."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, _ = cv2.split(hsv)
    mask = np.zeros(h.shape, dtype=np.uint8)
    for lo, hi in cfg.grid_hue_ranges:
        hue_in = cv2.inRange(h, int(lo), int(hi))
        mask = cv2.bitwise_or(mask, hue_in)
    # Only count as "grid" where the pixel is actually coloured (saturated).
    sat_mask = cv2.inRange(s, int(cfg.grid_min_saturation), 255)
    mask = cv2.bitwise_and(mask, sat_mask)
    # Thin grid lines → dilate slightly so inpainting covers anti-aliased edges.
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    return mask


def remove_grid(
    bgr: np.ndarray,
    cfg: PreprocessConfig | None = None,
    use_fft: bool = False,
) -> np.ndarray:
    """Return a grayscale image with the Rhodia grid suppressed.

    Parameters
    ----------
    bgr : np.ndarray
        Input colour scan (BGR uint8).
    cfg : PreprocessConfig
        Tunables (grid hue band, saturation threshold).
    use_fft : bool
        Apply an additional FFT notch filter for residual periodic lines.
    """
    cfg = cfg or PreprocessConfig()
    mask = _grid_color_mask(bgr, cfg)

    # Inpaint the chromatic grid using surrounding paper/pencil values.
    cleaned = cv2.inpaint(bgr, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    gray = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY)

    if use_fft:
        gray = _fft_notch(gray)
    return gray


def _fft_notch(gray: np.ndarray) -> np.ndarray:
    """Suppress dominant periodic frequencies (grid) via an FFT notch filter."""
    f = np.fft.fftshift(np.fft.fft2(gray.astype(np.float32)))
    mag = np.log1p(np.abs(f))
    h, w = gray.shape
    cy, cx = h // 2, w // 2

    # Find strong off-centre spectral peaks (the grid's fundamental harmonics)
    # and notch them, keeping the DC / low-frequency content (the drawing).
    peak = mag.copy()
    cv2.circle(peak, (cx, cy), max(h, w) // 20, 0, -1)  # ignore low freqs
    thr = peak.mean() + 3.5 * peak.std()
    ys, xs = np.where(peak > thr)
    for y, x in zip(ys, xs):
        cv2.circle(f.real, (x, y), 3, 0, -1)
        cv2.circle(f.imag, (x, y), 3, 0, -1)

    out = np.fft.ifft2(np.fft.ifftshift(f)).real
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out
