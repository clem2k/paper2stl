# Paper2STL — Sketch-to-STL pipeline

![Paper2STL](captures/out.jpg)

Reconstruct a **watertight `.stl`** solid from **scanned orthographic pencil
sketches** drawn on grid paper.

> 📖 **New here?** Read the [**USER_MANUAL.md**](USER_MANUAL.md) — how to draw,
> how many sheets to scan, and what every parameter does to the generated STL.
>
> 💻 **Just want to run it?** See [**INSTALL.md**](INSTALL.md).

The pipeline reads a folder of scans (one orthographic view per page — *top,
front, bottom, rear, left, right*), removes the printed grid, vectorises the
hand-drawn lines, classifies each view from its cartouche, reconstructs a 3D
volume via a **voxel visual hull**, infers any **missing views**, applies
**detail-page** features referenced by red frames, and exports an STL.

```
scans/ ──► [A] preprocess ──► [B] metadata ──► [C] reconstruct ──► [D] export ──► model.stl
```

---

## AI disclaimer

This project was made with Claude and Copilot helping to write and refactor code, and to draft documentation.
All ideas, design decisions, and final code are the author's own. The AI was used as a tool to assist in development.

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

**End users** download the prebuilt app; **developers** install from source:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                 # core only — the GUI runs fully on this
```

Full per-platform instructions (the macOS app, Windows, optional GPU/OCR
modules) are in [**INSTALL.md**](INSTALL.md).

The **core** (numpy, OpenCV, scikit-image, trimesh, PySide6) runs on CPU with no
models. Optional heavy extras are installed on demand:

- **OCR** (`easyocr` *or* `pytesseract`) — reads the view keyword from the
  cartouche. Without it, the pipeline falls back to the **filename**
  (`front.jpg`, `top.jpg`, …).
- **PyTorch** — only needed for neural line-straightening / 3D completion.

Both can be added later from the GUI's **Modules** menu, or with
`pip install ".[neural,ocr]"`.

### Hardware acceleration

Any deep-learning component selects the device dynamically:

```
CUDA (Nvidia) > MPS (Apple Silicon) > CPU
```

Check what was detected:

```bash
python -m paper2stl --info        # e.g. "compute device = mps (Apple Silicon GPU)"
```

---

## Quick start

A ready-to-run example (the *flipper* part, 6 views) ships in the repo — no
models required:

```bash
python -m paper2stl examples/flipper -o out.stl -v
# ✓ STL written to out.stl   (watertight)
```

Or launch the graphical interface and drag each scan into its slot:

```bash
python -m paper2stl --gui         # or: paper2stl-gui
```

In the GUI, the **Modules** menu installs the optional PyTorch / OCR components
on demand (it detects your OS and GPU and runs the right command).

---

## CLI

```
python -m paper2stl INPUT_DIR [-o OUT.stl] [options]

  -c, --config FILE       YAML config (see config/default.yaml)
  --device {cuda,mps,cpu} force compute device
  --resolution N          voxel grid resolution on the longest axis (default 256)
  --no-fill-missing       disable mirroring of missing opposite views
  --neural-weights FILE   enable reprojection-constrained neural completion
  --size-mm N             rescale the longest dimension to N millimetres
  -v / -vv                verbosity
  --info                  print detected device and exit
  --gui                   launch the graphical interface
```

Input scans may be named by view (`front.jpg`) or carry the keyword in the
upper-right cartouche; both English and common French terms are recognised
(*face, dessus, gauche, …*).

---

## Architecture

```
paper2stl/
├── cli.py / __main__.py        # command-line entry point
├── config.py                   # typed config (YAML-loadable)
├── device.py                   # CUDA / MPS / CPU resolver
├── pipeline.py                 # orchestrator (folder of scans → STL)
│
├── preprocessing/              # [A]
│   ├── grid_removal.py         #   HSV colour mask + inpaint
│   ├── binarize.py             #   CLAHE + adaptive threshold → pencil strokes
│   ├── vectorize.py            #   Hough + TLS refit → segments + silhouette
│   └── regularize.py           #   snap silhouettes to clean rectangles / axes
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
├── gui/                        # PySide6 desktop interface (+ Modules installer)
└── utils/                      # io + geometry helpers

config/default.yaml             # all tunables
examples/flipper/               # ready-to-run demo scans (6 views)
tests/                          # core pipeline tests (no OCR/torch needed)
```

---

## Programmatic use

```python
from paper2stl import Pipeline, PipelineConfig

cfg = PipelineConfig()
cfg.reconstruction.voxel_resolution = 160
cfg.export.target_size_mm = 100            # physical size of the longest edge

Pipeline(cfg).run("examples/flipper", "model.stl")
```

Already have clean silhouettes? Skip preprocessing/OCR:

```python
from paper2stl import Pipeline
sil = {"front": front_mask, "top": top_mask, "right": right_mask}  # uint8 0/255
Pipeline().run_on_silhouettes(sil, "model.stl")
```

---

## Tests

```bash
pip install -e ".[dev]"
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

---

## License

MIT — see [LICENCE](LICENCE).
