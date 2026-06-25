# Releasing Paper2STL

This is the **maintainer** guide for building and publishing the desktop app.
End-user install steps live in [INSTALL.md](INSTALL.md).

The app is distributed as a **small, self-bootstrapping bundle** (~300 KB). It
contains only the source; on its first launch it creates a private virtual
environment and installs the dependencies from PyPI (~400 MB, once). Subsequent
launches are instant.

> Why not a single "all-in-one" binary? It would weigh ~2 GB (PySide6/OpenCV,
> and PyTorch if bundled). Here the distributed artifact stays tiny; the user's
> machine downloads only what it needs.

---

## macOS

### Build

On a Mac, from the repository root:

```bash
./scripts/build_installer_app.sh
```

This produces `dist/Paper2STL.app`. Zip it and publish:

```bash
cd dist
zip -r -y Paper2STL-mac.zip Paper2STL.app      # -y preserves the bundle's symlinks
# → attach Paper2STL-mac.zip to a GitHub Release
```

Nothing else to compile.

### What the app does

- **Launcher** (`Contents/MacOS/Paper2STL`): if the venv + install marker exist,
  it runs the GUI directly; otherwise it opens the first-run installer in
  Terminal.
- **Bootstrap** (`Contents/Resources/bootstrap.command`): finds Python 3.10+,
  creates the venv (robustly — it revalidates and rebuilds an incomplete one,
  with a PID lock against double-launch), installs the **core** package from the
  bundled source, writes the marker, and relaunches the app.

### Gatekeeper

A downloaded, unsigned app needs **right-click ▸ Open** the first time. The app
is ad-hoc signed by the build script, which reduces friction but does not remove
this step. Removing it entirely requires an Apple Developer ID + notarisation
(~$99/year).

### File locations

| Item | Path |
|---|---|
| Virtual environment + dependencies | `~/Library/Application Support/Paper2STL/venv` |
| "Already installed" marker | `…/venv/.paper2stl_installed` |
| The app itself | wherever the user put it (Applications, Desktop…) |

**Reset / force a clean reinstall:**

```bash
rm -rf ~/Library/Application\ Support/Paper2STL
```

The next launch reinstalls from scratch.

### Refresh an installed venv after a source change

To push updated source into an existing venv without re-downloading the heavy
dependencies:

```bash
~/Library/Application\ Support/Paper2STL/venv/bin/python \
    -m pip install --no-deps --force-reinstall .
```

---

## Windows

The Windows flow mirrors macOS exactly. `scripts/build_installer_app.ps1` is the
analogue of the `.sh` script.

> ⚠️ **Must be built on Windows** — the PowerShell script cannot run from macOS.

### Build

From the repository root, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer_app.ps1
```

This produces `dist\Paper2STL\` and zips it to `dist\Paper2STL-windows.zip`,
ready to attach to a GitHub Release.

### What the app does

- **Launcher** (`Paper2STL.cmd`): if the venv + install marker exist, it starts
  the GUI with `pythonw.exe` (no console); otherwise it runs the first-run
  installer in a visible console.
- **Bootstrap** (`resources\bootstrap.ps1`): finds Python 3.10+ (via the `py`
  launcher or `python`), creates the venv (robustly — revalidates and rebuilds
  an incomplete one, with a PID lock against double-launch and an `ensurepip`
  fallback), installs the **core** package from the bundled source, writes the
  marker, creates a Desktop shortcut, and launches the GUI.

### SmartScreen

The app is unsigned, so the first launch shows a SmartScreen prompt — the user
clicks **More info ▸ Run anyway**. Authenticode signing (signtool + a code-signing
certificate) would remove it; not required for distribution.

### File locations

| Item | Path |
|---|---|
| Virtual environment + dependencies | `%LOCALAPPDATA%\Paper2STL\venv` |
| "Already installed" marker | `…\venv\.paper2stl_installed` |
| Desktop shortcut | `%USERPROFILE%\Desktop\Paper2STL.lnk` |

**Reset / force a clean reinstall:** delete `%LOCALAPPDATA%\Paper2STL`. The next
launch reinstalls from scratch.

---

## Optional modules in the shipped app

The released app installs the **core** only. Users add PyTorch / OCR on demand
from the in-app **Modules** menu (it picks the OS/GPU-correct pip command). No
release rebuild is needed for that.
