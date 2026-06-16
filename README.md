# Rhodia — Sketch-to-STL pipeline

Reconstruct a **watertight `.stl`** solid from **scanned orthographic pencil
sketches** drawn on Rhodia grid paper.

The pipeline reads a folder of scans (one orthographic view per page — *top,
front, bottom, rear, left, right*), removes the printed grid, vectorises the
hand-drawn lines, classifies each view from its cartouche, reconstructs a 3D
volume via a **voxel visual hull**, infers any **missing views**, applies
**detail-page** features referenced by red frames, and exports an STL.

```
scans/ ──► [A] preprocess ──► [B] metadata ──► [C] reconstruct ──► [D] export ──► model.stl
```

---

## Why a voxel visual hull (and how missing views are handled)

Orthographic silhouettes only constrain a **visual hull**: the intersection of
the prisms obtained by extruding each silhouette along its view axis. This is
exact and dimensionally faithful for the observed directions, and — because we
work in a **voxel grid** meshed with **marching cubes** — the result is a
**closed manifold by construction** (no fragile mesh booleans).

Missing views are filled by a cascade of priors, weakest last:

| Layer | Role | Trigger |
|---|---|---|
| **Voxel visual hull** | exact, watertight core | always |
| **Opposite-view symmetry** | mirror `left`→`right`, `top`→`bottom`, … | opposite view absent |
| **Bounded extrusion** | a lone view becomes a finite slab, not an infinite prism | an axis observed by no view |
| **Neural completion** *(opt-in)* | learned shape prior, **re-projected under the observed silhouettes** so it can never violate them | `--neural-weights` |

The neural model never *replaces* the hull — its output is intersected back
with every observed silhouette, preserving dimensional coherence.

---

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The **core** (numpy, OpenCV, scikit-image, trimesh) runs on CPU with no models.
Optional extras:

- **OCR** (`easyocr` *or* `pytesseract` + the Tesseract binary) — reads the view
  keyword from the cartouche. Without it, the pipeline falls back to the
  **filename** (`front.png`, `top.png`, …).
- **PyTorch** — only needed for neural line-straightening / 3D completion.

### Hardware acceleration

Any deep-learning component selects the device dynamically:

```
CUDA (Nvidia) > MPS (Apple Silicon) > CPU
```

Check what was detected:

```bash
python -m rhodia --info        # e.g. "compute device = mps (Apple Silicon GPU)"
```

Install the matching PyTorch wheel for CUDA / MPS as per
<https://pytorch.org/get-started/locally/>.

---

## Quick start (runnable demo, no models required)

```bash
# 1. Generate synthetic Rhodia scans of an L-bracket (3 views).
python examples/generate_synthetic.py --out examples/scans --shape lbracket

# 2. Reconstruct an STL.
python -m rhodia examples/scans -o examples/out.stl -v
# ✓ STL written to examples/out.stl   (watertight, X:Y:Z ≈ 1:0.6:1)
```

Try a **box with a red detail frame**, or fewer views to exercise inference:

```bash
python examples/generate_synthetic.py --out examples/scans --shape box --with-detail
python -m rhodia examples/scans -o examples/out.stl -vv
```

---

## CLI

```
python -m rhodia INPUT_DIR [-o OUT.stl] [options]

  -c, --config FILE       YAML config (see config/default.yaml)
  --device {cuda,mps,cpu} force compute device
  --resolution N          voxel grid resolution on the longest axis (default 128)
  --no-fill-missing       disable mirroring of missing opposite views
  --neural-weights FILE   enable reprojection-constrained neural completion
  --size-mm N             rescale the longest dimension to N millimetres
  -v / -vv                verbosity
  --info                  print detected device and exit
```

Input scans may be named by view (`front.png`) or carry the keyword in the
upper-right cartouche; both English and common French terms are recognised
(*face, dessus, gauche, …*).

---

## Architecture

```
rhodia/
├── cli.py / __main__.py        # command-line entry point
├── config.py                   # typed config (YAML-loadable)
├── device.py                   # CUDA / MPS / CPU resolver
├── pipeline.py                 # orchestrator (folder of scans → STL)
│
├── preprocessing/              # [A]
│   ├── grid_removal.py         #   HSV colour mask + inpaint (+ optional FFT notch)
│   ├── binarize.py             #   CLAHE + adaptive threshold → pencil strokes
│   └── vectorize.py            #   Hough + TLS refit → straight segments + silhouette
│
├── metadata/                   # [B]
│   ├── ocr.py                  #   cartouche OCR → view classification (fuzzy)
│   └── red_frames.py           #   red-frame detection + interior OCR (detail refs)
│
├── reconstruction/             # [C]
│   ├── views.py                #   image→3D axis convention, opposites
│   ├── align.py                #   shared-axis registration → voxel bounding box
│   ├── csg_recon.py            #   extrude + intersect → voxel visual hull
│   ├── infer_missing.py        #   opposite-view mirroring, unconstrained axes
│   ├── neural_recon.py         #   optional 3D U-Net completion (reprojection-constrained)
│   └── reconstruct.py          #   stage C orchestration
│
├── detail_pages/
│   └── apply_details.py        #   stamp detail features as local CSG (pocket/boss)
│
├── export/                     # [D]
│   └── mesh_export.py          #   marching cubes → Taubin smooth → repair → STL
│
└── utils/                      # io + geometry helpers

config/default.yaml             # all tunables
examples/generate_synthetic.py  # demo scan generator
tests/                          # core pipeline tests (no OCR/torch needed)
```

---

## Programmatic use

```python
from rhodia import Pipeline, PipelineConfig

cfg = PipelineConfig()
cfg.reconstruction.voxel_resolution = 160
cfg.export.target_size_mm = 100            # physical size of the longest edge

Pipeline(cfg).run("examples/scans", "model.stl")
```

Already have clean silhouettes? Skip preprocessing/OCR:

```python
import numpy as np
from rhodia import Pipeline
sil = {"front": front_mask, "top": top_mask, "right": right_mask}  # uint8 0/255
Pipeline().run_on_silhouettes(sil, "model.stl")
```

---

## Tests

```bash
pip install pytest
python -m pytest tests/ -q
```

The tests cover the axis convention, visual-hull carving, missing-view
inference and watertight export — and run **without** OCR or PyTorch installed.

---

## Limitations & next steps

- The visual hull cannot recover concavities invisible from every silhouette
  (e.g. a fully internal cavity). Enable neural completion, or model such
  features explicitly as detail pages.
- Hand-drawn perspective/oblique strokes are assumed already orthographic; a
  learned wireframe parser can be plugged into `preprocessing/vectorize.py`.
- Detail-page placement currently maps a referenced scan to a pocket/boss at
  the red frame's location; richer feature semantics can extend `DetailPage`.
