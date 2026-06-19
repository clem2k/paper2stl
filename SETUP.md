# Setup guide

This guide walks through installing **Paper2STL** on every supported platform.

The pipeline has two layers of dependencies:

- **Core + optional extras** — listed in [`requirements.txt`](requirements.txt).
  These are the same everywhere (numpy, OpenCV, trimesh, OCR, GUI, …).
- **PyTorch** — needed only for neural line-straightening / 3D completion. The
  right wheel depends on your OS **and** whether you have an Nvidia GPU. This is
  the only part that differs per platform.

> **Why a separate torch step?** On Windows the default `torch` wheel on PyPI is
> **CPU-only**. If you simply `pip install torch` you will *not* get CUDA, even
> with an Nvidia GPU. To force the GPU build you must point pip at the PyTorch
> CUDA index **and** pin an exact `+cuXXX` version — PEP 440 only allows the
> `+cu121` local label with `==`, never with `>=`.

After installing, always confirm the detected device:

```bash
python -m paper2stl --info
# → "compute device = cuda (Nvidia CUDA GPU)"   (or mps / cpu)
```

---

## 1. Create and activate a virtual environment

Pick the command block for your shell.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**macOS / Linux (bash/zsh):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

---

## 2. Install per platform

### Windows + CUDA (Nvidia GPU)

The default PyPI `torch` is CPU-only on Windows, so install torch from the
PyTorch CUDA index. The repo already ships the correct pins in
[`requirements-cuda.txt`](requirements-cuda.txt):

```powershell
# core + optional extras (note: this would pull CPU torch — installed/overridden next)
pip install -r requirements.txt

# replace torch/torchvision with the CUDA (cu121) build
pip install -r requirements-cuda.txt
```

If torch was already installed as CPU-only, force the swap:

```powershell
pip uninstall -y torch torchvision
pip install -r requirements-cuda.txt
```

`requirements-cuda.txt` contains:

```
--extra-index-url https://download.pytorch.org/whl/cu121
torch==2.5.1+cu121
torchvision==0.20.1+cu121
```

> **Driver requirement:** cu121 wheels need an Nvidia driver new enough for
> CUDA 12.1 (driver ≥ 530). The CUDA *toolkit* itself is bundled in the wheel —
> you do **not** need to install CUDA separately. For a newer CUDA series, swap
> the index (e.g. `cu124`) and bump the pins to a matching torch version from
> <https://pytorch.org/get-started/locally/>.

Verify:

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# → 2.5.1+cu121 True
```

### Windows without CUDA (CPU only)

Just the core requirements; the default PyPI torch wheel is already CPU-only:

```powershell
pip install -r requirements.txt
```

To be explicit (and avoid accidentally pulling a GPU build), you can pin the CPU
index:

```powershell
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Verify:

```powershell
python -m paper2stl --info     # → compute device = cpu
```

### macOS (Apple Silicon — MPS, or Intel — CPU)

macOS has **no CUDA**. The standard PyPI torch wheel already supports Apple's
**MPS** GPU backend on Apple Silicon (M1/M2/M3/M4) and falls back to CPU on Intel
Macs. No special index is needed:

```bash
pip install -r requirements.txt
```

Verify:

```bash
python -m paper2stl --info
# Apple Silicon → compute device = mps (Apple Silicon GPU)
# Intel Mac     → compute device = cpu
```

### Linux + CUDA (Nvidia GPU)

Unlike Windows, the default PyPI `torch` wheel on Linux **already bundles CUDA**,
so the core install usually gives you GPU support out of the box:

```bash
pip install -r requirements.txt
```

If you need a specific CUDA series (e.g. to match your driver), install torch
from the matching index instead. Using the same cu121 pins as Windows:

```bash
pip uninstall -y torch torchvision
pip install -r requirements-cuda.txt
```

> **Driver requirement:** the cu121 wheels need an Nvidia driver supporting
> CUDA 12.1 (driver ≥ 530). The toolkit ships inside the wheel — no system CUDA
> install required. Pick a different index (cu118 / cu124 / …) from
> <https://pytorch.org/get-started/locally/> if your driver is older or newer.

Verify:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -m paper2stl --info     # → compute device = cuda
```

### Linux without CUDA (CPU only)

Force the CPU-only torch index so you don't download the large CUDA wheel:

```bash
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Verify:

```bash
python -m paper2stl --info     # → compute device = cpu
```

---

## 3. Optional components

| Feature | Needs | Notes |
|---|---|---|
| **OCR (cartouche → view name)** | `easyocr` **or** `pytesseract` | EasyOCR pulls torch automatically. Tesseract also needs the system binary (`apt install tesseract-ocr`, `brew install tesseract`, or the Windows installer). Without OCR the pipeline falls back to filenames (`front.png`, …). |
| **Neural completion / line-straightening** | `torch`, `torchvision` | Only used with `--neural-weights`. Pick the wheel per the tables above. |
| **GUI** (`python -m paper2stl --gui`) | `PySide6` | Included in `requirements.txt`. |
| **Richer mesh tooling** | `open3d` | Optional; only installs on Python < 3.12. |

---

## 4. Run the tests (no GPU / OCR required)

```bash
pip install pytest
python -m pytest tests/ -q
```

---

## Troubleshooting

- **`cuda available: False` on Windows despite an Nvidia GPU** — you have the
  CPU wheel. Run the *Windows + CUDA* swap above
  (`pip uninstall -y torch torchvision` then `pip install -r requirements-cuda.txt`).
- **`Invalid requirement: 'torch>=2.5+cu121'`** — a `+cuXXX` local label can only
  be used with `==`. Pin the exact version (`torch==2.5.1+cu121`).
- **`pin_memory ... no accelerator is found` warning** — harmless, but it means
  torch is running on CPU. Install the CUDA/MPS build to use the GPU.
- **Driver too old for cu121** — update your Nvidia driver, or choose an older
  CUDA index (cu118) from <https://pytorch.org/get-started/locally/>.
