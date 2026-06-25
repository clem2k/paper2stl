# Installing Paper2STL

Paper2STL ships as a **lightweight** application: the download is just the
source (a few MB). The heavy dependencies are fetched once, automatically, the
first time you launch it.

There are two ways to install, depending on who you are:

- **End user** → download the prebuilt app (no command line). *macOS and
  Windows.*
- **Developer / contributor** → install from source with `pip`.

> **Optional heavy modules** (PyTorch for neural completion, EasyOCR/Tesseract
> for reading the title block) are **not** required. They are installed on
> demand from inside the app — see [Optional modules](#optional-modules) — or
> with `pip install ".[neural,ocr]"`.

---

## macOS

### Option A — Prebuilt app (recommended)

1. Download **`Paper2STL-mac.zip`** from the
   [Releases page](../../releases) and double-click it to unzip.
2. **Right-click** `Paper2STL.app` ▸ **Open**, then confirm.
   *(Required only the first time: macOS blocks apps that are not signed by a
   paid Apple Developer account; right-click ▸ Open authorises it once.)*
3. On the **first launch**, a Terminal window opens and installs the
   environment (~400 MB, a few minutes). Let it finish — the app then starts on
   its own.
4. Every launch after that is instant.

**Requirement:** Python 3.10 or newer. If it is missing, the installer opens the
download page <https://www.python.org/downloads/macos/> automatically; install
Python, then relaunch the app.

### Option B — From source (developers)

```bash
git clone <repo-url> paper2stl && cd paper2stl
python3 -m venv .venv && source .venv/bin/activate
pip install -e .          # core only (CPU); the GUI runs fully on this
```

Launch:

```bash
paper2stl-gui             # or: python -m paper2stl --gui
```

The default PyPI PyTorch wheel already supports Apple's **MPS** GPU backend on
Apple Silicon (M1–M4) and falls back to CPU on Intel Macs — no special index is
needed if you add the neural extras.

---

## Windows

### Option A — Prebuilt app (recommended)

1. Download **`Paper2STL-windows.zip`** from the
   [Releases page](../../releases) and unzip it (right-click ▸ *Extract All…*).
2. Open the `Paper2STL` folder and **double-click `Paper2STL.cmd`**.
   If Windows SmartScreen warns, click **More info ▸ Run anyway** (it appears
   because the app is not signed by a paid certificate).
3. On the **first launch**, a console window installs the environment
   (~400 MB, a few minutes) and adds a **Paper2STL** shortcut to your Desktop.
   When it finishes, the app starts on its own.
4. From then on, launch it from the **Desktop shortcut** — it opens instantly,
   with no console window.

**Requirement:** Python 3.10 or newer. If it is missing, the installer opens the
download page <https://www.python.org/downloads/windows/> automatically. When
installing Python, tick **"Add python.exe to PATH"**, then relaunch.

### Option B — From source (developers)

```powershell
git clone <repo-url> paper2stl
cd paper2stl
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
python -m paper2stl --gui
```

**PyTorch on Windows (only if you want neural completion):** the default PyPI
`torch` wheel is **CPU-only** on Windows. For an Nvidia GPU, install the CUDA
build explicitly (or just use the in-app **Modules** menu, which picks the right
command for you):

```powershell
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 `
    --index-url https://download.pytorch.org/whl/cu121
```

A CUDA 12.1 wheel needs an Nvidia driver ≥ 530. The CUDA toolkit ships inside
the wheel — you do **not** need to install CUDA separately.

---

## Linux (from source)

```bash
git clone <repo-url> paper2stl && cd paper2stl
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m paper2stl --gui
```

On Linux the default PyPI `torch` wheel already bundles CUDA, so adding the
neural extras gives GPU support out of the box. Force the CPU build with
`--index-url https://download.pytorch.org/whl/cpu` if you do not have an Nvidia
GPU and want a smaller download.

---

## Optional modules

You only need these for specific features; the core app does not require them.

| Module | Adds | Size |
|---|---|---|
| **PyTorch** | Neural line-straightening and 3D completion (`--neural-weights`) | ~2 GB |
| **EasyOCR** | Reads the title block to name views automatically (pulls PyTorch) | ~2 GB |
| **Tesseract** | Lighter OCR alternative; also needs the native Tesseract engine | small |

**Easiest way:** open the app and use the **Modules** menu ▸ *Modules
optionnels…*. It detects your OS/GPU and runs the correct install command,
streaming the progress. (On macOS it uses the Apple GPU automatically; on
Windows/Linux with an Nvidia GPU it offers a CUDA/CPU choice.)

**From the command line** (into the same environment):

```bash
pip install ".[neural]"     # PyTorch only
pip install ".[ocr]"        # EasyOCR + pytesseract
pip install ".[neural,ocr]" # both
```

Without OCR, the pipeline classifies views by **file name** (`front.jpg`,
`top.jpg`, …) — which is all the GUI needs, so OCR is genuinely optional.

---

## Verify

```bash
python -m paper2stl --info
# → compute device = mps (Apple Silicon GPU)     (or cuda / cpu)
```
