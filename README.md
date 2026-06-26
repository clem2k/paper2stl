# Paper2STL — Sketch-to-STL pipeline

> 🇫🇷 **Version française** : suivez ce lien → [**README_FR.md**](README_FR.md).

![Paper2STL](res/logo.jpg)

Reconstruct a **watertight `.stl`** solid from **scanned orthographic pencil
sketches** drawn on grid paper.

---

## 🧩 The Big Picture

Draw a part by hand — one orthographic view per sheet (*top, front, bottom,
rear, left, right*) — scan the pages, and Paper2STL turns them into a printable
3D model.

Under the hood it reads the folder of scans, removes the printed grid,
vectorises the pencil lines, figures out which view each page is, reconstructs a
3D volume from the silhouettes, fills in any missing views, stamps on
**detail-page** features marked by red frames, and writes an STL.

```
scans/ ──► [A] preprocess ──► [B] metadata ──► [C] reconstruct ──► [D] export ──► model.stl
```

### For best results
You can use any paper to use this application, but I found that I was more comfortable and got better results with graph paper (millimeter or centimeter) and a hard pencil (HB or 2H). The printed grid is automatically removed, and the pencil lines are easier to vectorize when they are thin and high-contrast. I have been using RODHIA notebooks for years and get very satisfactory results for my personal use.

<p>
  <img src="res/1000055697.jpg" width="30%" />
  <img src="res/1000055703.jpg" width="30%" />
  <img src="res/1000055698.jpg" width="30%" />
</p>


### Contributing to the project
You can contribute to the project by suggesting improvements, reporting bugs, or adding new features. Feel free to open an issue on GitHub or submit a pull request. For developers, the code is written in Python 3.10+ and uses popular libraries like NumPy, OpenCV, scikit-image, trimesh, and PySide6. Contributions are welcome!

### How it works

There are **two ways to use it**, pick yours:

| | [🚀 Easy Mode](#-easy-mode) | [🐍 Pro Mode](#-pro-mode) |
|---|---|---|
| **For** | anyone | people comfortable with Python |
| **How** | download the app, click | command line + source install |
| **Needs** | python 3.10+ | Python 3.10+, a terminal |
| **Gets you** | the graphical interface | every tunable option + the API |

> 📖 Whichever mode you choose, the [**USER_MANUAL.md**](USER_MANUAL.md)
> explains *how to draw*, how many sheets to scan, and what each parameter does
> to the generated STL.

> 🤖 **AI disclaimer.** This project was made with Claude and Copilot helping to
> write/refactor code and draft documentation. All ideas, design decisions, and
> final code are the author's own — the AI was used as a tool.

---

## 🚀 Easy Mode

**No Python. No command line. Just download, click, and drop your scans in.**

### 1 — Get the app

Grab the prebuilt bundle from the [**Releases page**](../../releases):

- **macOS** → `Paper2STL-mac.zip`
- **Windows** → `Paper2STL-windows.zip`

The download is tiny (a few MB — only the source). The first time you launch it,
it quietly sets up everything it needs (~400 MB, once) and then starts on its
own. Every launch after that is instant.

> The app is **fully portable**: everything lives next to the launcher. Delete
> the folder and nothing is left behind — nothing is ever written to your user
> profile or the registry.


### 2 — Use the graphical interface

![The Paper2STL graphical interface](res/cap.png)

1. **Drop a scan onto each face card** on the left (*Front, Top, Left, Rear /
   Back, Bottom, Right*) — or click a card to browse. You don't need all six;
   missing views are inferred.
2. *(Optional)* add a **Detail zone** for scans marked with a red cartouche that
   zoom into a sub-region of a face.
3. Set the **Output** path (top right) — the full path of the `.stl` to write.
4. Tweak anything you like in the **parameters panel** on the right (all
   collapsible): *Device & OCR, Grid removal, Pencil extraction, Line detection
   & merging, Shape regularisation, …*. The defaults work out of the box, so you
   can ignore this entirely.
5. Click **▶ Run** (or `Ctrl+R`). Progress and a live log show at the bottom.

### Optional add-ons

The app installs the lightweight **core** only. If you want the extras —
**PyTorch** (neural shape completion) or **OCR** (reads the view label from the
cartouche so scans don't have to be named `front.jpg`, `top.jpg`, …) — open the
**Modules** menu. It detects your OS and GPU and runs the right install command
for you. No rebuild, no terminal.

### About / reset

- **Aide ▸ À propos…** shows the version, author, and licence.
- To start fresh, just delete the app folder and unzip the download again.

---

## 🐍 Pro Mode

**For developers.** Requires Python skills, a terminal, and Python 3.10+.
This mode gives you the full command line, every tunable parameter, and the
Python API.

### Install from source

```bash
git clone https://www.github.com/clem2k/paper2stl && cd paper2stl
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                 # core only — the GUI runs fully on this
```

The **core** (numpy, OpenCV, scikit-image, trimesh, PySide6) runs on CPU with no
models. Optional heavy extras are installed on demand:

- **OCR** (`easyocr` *or* `pytesseract`) — reads the view keyword from the
  cartouche. Without it, the pipeline falls back to the **filename**
  (`front.jpg`, `top.jpg`, …).
- **PyTorch** — only needed for neural line-straightening / 3D completion.

Add them with `pip install ".[neural,ocr]"`, or later from the GUI's **Modules**
menu.

### Quick start

A ready-to-run example (the *flipper* part, 6 views) ships in the repo — no
models required:

```bash
python -m paper2stl examples/flipper -o out.stl -v
# ✓ STL written to out.stl   (watertight)
```

Or launch the same graphical interface as Easy Mode:

```bash
python -m paper2stl --gui         # or: paper2stl-gui
```

### Command line

```
python -m paper2stl INPUT_DIR [-o OUT.stl] [options]
```

| Option | Default | Effect |
|---|---|---|
| `-o, --output FILE` | `output.stl` | output STL path |
| `-c, --config FILE` | — | YAML config (see [`config/default.yaml`](config/default.yaml)) |
| `--device {cuda,mps,cpu}` | auto | force the compute device |
| `--resolution N` | 256 | voxel grid resolution on the longest axis |
| `--size-mm N` | — | rescale the longest dimension to N millimetres |
| `--no-fill-missing` | off | disable mirroring of missing opposite views |
| `--neural-weights FILE` | — | enable reprojection-constrained neural completion |
| `--no-align` | off | disable cross-view registration (crop-and-stretch instead) |
| `--align-tolerance FRAC` | 0.15 | how far a view may be nudged to register (fraction of axis length); 0 disables the shift search |
| `--ocr-backend {auto,easyocr,tesseract,none}` | auto | view-label OCR backend; `none` classifies by file name only (much faster) |
| `--grid-tolerance N` | 0.0 | grid-removal tolerance; negative = stricter, positive = more aggressive |
| `--pencil-strength N` | 55 | ink contrast floor — how much darker than the paper a stroke must be; `0` = legacy adaptive threshold |
| `--straighten-pct PCT` | 100 | line straightening 0–100; `100` = fully straight (TLS refit), `0` = raw Hough endpoints (keeps curves) |
| `--no-regularize` | off | keep the raw hand-drawn outline instead of snapping to clean rectangles/edges |
| `--rect-score FRAC` | 0.90 | rectangleness threshold 0–1: a silhouette filling at least this fraction of its bounding rect collapses to a perfect rectangle |
| `--angle-snap-deg DEG` | 10 | snap silhouette edges within this many degrees of a dominant axis to exactly straight |
| `--presmooth-sigma SIGMA` | 0.6 | Gaussian pre-smoothing (voxels) before marching cubes; `0` disables it |
| `--debug-dir DIR` | — | save per-page debug images (grid removal, binary strokes, segments, silhouette) as JPEGs |
| `-v / -vv` | — | verbosity |
| `--info` | — | print the detected compute device and exit |
| `--gui` | — | launch the graphical interface |

Input scans may be named by view (`front.jpg`) or carry the keyword in the
upper-right cartouche; both English and common French terms are recognised
(*face, dessus, gauche, …*).

### Hardware acceleration

Any deep-learning component selects the device dynamically:

```
CUDA (Nvidia) > MPS (Apple Silicon) > CPU
```

Check what was detected:

```bash
python -m paper2stl --info        # e.g. "compute device = mps (Apple Silicon GPU)"
```

### Why a voxel visual hull (and how missing views are handled)

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

### Programmatic use

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

### Architecture

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

### Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -q
```

The tests cover the axis convention, visual-hull carving, missing-view
inference and watertight export — and run **without** OCR or PyTorch installed.

### Limitations & next steps

- The visual hull cannot recover concavities invisible from every silhouette
  (e.g. a fully internal cavity). Enable neural completion, or model such
  features explicitly as detail pages.
- Hand-drawn perspective/oblique strokes are assumed already orthographic; a
  learned wireframe parser can be plugged into `preprocessing/vectorize.py`.
- Detail-page placement currently maps a referenced scan to a pocket/boss at the
  red frame's location; richer feature semantics can extend `DetailPage`.

---

## License

MIT — see [LICENCE](LICENCE).
