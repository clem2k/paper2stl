#!/usr/bin/env python3
"""Assemble the Windows Paper2STL app — runnable from ANY OS (macOS included).

The Windows bundle contains no compiled code: just the Python source plus two
text launchers (``Paper2STL.cmd`` and ``resources/bootstrap.ps1``). So it can be
built anywhere with nothing but Python — you do **not** need Windows or
PowerShell to produce it. The bundled ``bootstrap.ps1`` runs on the *end user's*
Windows machine on first launch (creates a venv under %LOCALAPPDATA% and
pip-installs the core package from PyPI, ~400 MB once).

Usage (e.g. on your Mac):

    python3 scripts/build_windows.py

Output:

    dist/Paper2STL/                the app folder (user double-clicks Paper2STL.cmd)
    dist/Paper2STL-windows.zip     ready to attach to a GitHub Release

This is the Windows analogue of scripts/build_installer_app.sh (which builds the
macOS .app and must run on a Mac because it uses codesign).
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "dist" / "Paper2STL"
RES = APP / "resources"
SRC = RES / "src"
ZIP = REPO / "dist" / "Paper2STL-windows.zip"

# ── Launcher (Paper2STL.cmd) ────────────────────────────────────────────────
# Fast path: venv ready → launch the GUI with pythonw (no console window).
# First run:  no venv  → run the bootstrap installer in a visible console.
LAUNCHER_CMD = r'''@echo off
setlocal
set "VENV=%LOCALAPPDATA%\Paper2STL\venv"
set "MARKER=%VENV%\.paper2stl_installed"
if exist "%VENV%\Scripts\pythonw.exe" if exist "%MARKER%" (
    start "" "%VENV%\Scripts\pythonw.exe" -m paper2stl.gui
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0resources\bootstrap.ps1"
'''

# ── First-run installer (resources/bootstrap.ps1) ───────────────────────────
BOOTSTRAP_PS1 = r'''# Paper2STL - first launch: automatic environment setup.
$ErrorActionPreference = 'Stop'
function Info($m) { Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "OK $m" -ForegroundColor Green }
function Warn($m) { Write-Host " ! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host ""; Write-Host "ERROR: $m" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

$Res     = Split-Path -Parent $MyInvocation.MyCommand.Path
$SrcDir  = Join-Path $Res 'src'
$Support = Join-Path $env:LOCALAPPDATA 'Paper2STL'
$Venv    = Join-Path $Support 'venv'
$Marker  = Join-Path $Venv '.paper2stl_installed'
$VPy     = Join-Path $Venv 'Scripts\python.exe'
$VPyw    = Join-Path $Venv 'Scripts\pythonw.exe'

Clear-Host
Write-Host "=== Paper2STL - First-time installation ===" -ForegroundColor White
Write-Host "This step runs only ONCE; later launches will be instant."
Write-Host ""

# -- find Python 3.10+ --
Info "Looking for Python 3.10 or newer..."
$found = $null
$cands = @(@('py','-3.13'),@('py','-3.12'),@('py','-3.11'),@('py','-3.10'),@('py','-3'),@('python'),@('python3'))
foreach ($c in $cands) {
    $exe  = $c[0]
    $rest = @(); if ($c.Count -gt 1) { $rest = $c[1..($c.Count - 1)] }
    try {
        $v = & $exe @rest -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) {
            $p = $v.Trim().Split('.')
            if ([int]$p[0] -ge 3 -and [int]$p[1] -ge 10) {
                $found = @{ Exe = $exe; Args = $rest; Ver = $v.Trim() }
                break
            }
        }
    } catch { }
}
if (-not $found) {
    Warn "Python 3.10+ not found."
    Write-Host "   Install Python from https://www.python.org/downloads/windows/ then relaunch."
    Start-Process "https://www.python.org/downloads/windows/"
    Die "Python 3.10+ is required."
}
Ok ("Found: Python " + $found.Ver)
Write-Host ""

New-Item -ItemType Directory -Force -Path $Support | Out-Null

# -- double-launch lock (self-healing via PID) --
$Lock = Join-Path $Support '.install.lock'
if (Test-Path $Lock) {
    $oldpid = (Get-Content (Join-Path $Lock 'pid') -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldpid -and (Get-Process -Id ([int]$oldpid) -ErrorAction SilentlyContinue)) {
        Warn "An installation is already running (PID $oldpid). Close the other window."
        Start-Sleep 4; exit 0
    }
    Remove-Item -Recurse -Force $Lock
}
New-Item -ItemType Directory -Force -Path $Lock | Out-Null
"$PID" | Out-File -FilePath (Join-Path $Lock 'pid') -Encoding ascii

try {
    function Test-Venv {
        if (-not (Test-Path $VPy)) { return $false }
        & $VPy -m pip --version *> $null
        return ($LASTEXITCODE -eq 0)
    }

    if (-not (Test-Venv)) {
        Info "Creating the environment..."
        if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }   # rebuild if incomplete
        & $found.Exe @($found.Args) -m venv $Venv
        if ($LASTEXITCODE -ne 0) { Die "Could not create the virtual environment." }
        # Guarantee pip inside the venv.
        & $VPy -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) { & $VPy -m ensurepip --upgrade *> $null }
        if (-not (Test-Venv)) { Die "Could not install pip into the environment." }
    }

    Info "Updating pip..."
    & $VPy -m pip install --upgrade pip --disable-pip-version-check

    Write-Host ""
    Info "Installing dependencies (~400 MB, one time)..."
    Write-Host "   Please wait - PySide6, OpenCV, NumPy are downloading."
    Write-Host ""
    & $VPy -m pip install "$SrcDir"
    if ($LASTEXITCODE -ne 0) { Die "Dependency installation failed." }

    New-Item -ItemType File -Force -Path $Marker | Out-Null
    Write-Host ""
    Ok "Installation complete."

    # Desktop shortcut (launches with pythonw -> no console window).
    try {
        $ws  = New-Object -ComObject WScript.Shell
        $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Paper2STL.lnk'))
        $lnk.TargetPath       = $VPyw
        $lnk.Arguments        = '-m paper2stl.gui'
        $lnk.WorkingDirectory = $Venv
        $lnk.Save()
        Ok "Desktop shortcut created."
    } catch { }

    Info "Launching Paper2STL..."
    Start-Process $VPyw -ArgumentList '-m', 'paper2stl.gui'
}
finally {
    Remove-Item -Recurse -Force $Lock -ErrorAction SilentlyContinue
}
'''


def _write(path: Path, text: str) -> None:
    """Write *text* with Windows CRLF line endings."""
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))


def main() -> int:
    print(">> Cleaning previous build...")
    if APP.exists():
        shutil.rmtree(APP)
    if ZIP.exists():
        ZIP.unlink()
    SRC.mkdir(parents=True)

    # 1. bundle source (exclude caches; tests live outside the package)
    print(">> Bundling source...")
    shutil.copytree(
        REPO / "paper2stl", SRC / "paper2stl",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(REPO / "pyproject.toml", SRC)
    for opt in ("README.md", "LICENCE"):
        if (REPO / opt).exists():
            shutil.copy2(REPO / opt, SRC)
    print(f"OK source bundled ({sum(1 for _ in SRC.rglob('*'))} files)")

    # 2. launcher + 3. first-run installer
    print(">> Writing launcher and first-run installer...")
    _write(APP / "Paper2STL.cmd", LAUNCHER_CMD)
    _write(RES / "bootstrap.ps1", BOOTSTRAP_PS1)

    # 4. zip (top-level folder = Paper2STL/)
    print(">> Creating Paper2STL-windows.zip...")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(APP.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(APP.parent))

    size_mb = ZIP.stat().st_size / 1e6
    print(f"\nOK Built {APP}")
    print(f"   {ZIP}  ({size_mb:.1f} MB)")
    print("\n  Distribute: upload dist/Paper2STL-windows.zip to GitHub Releases.")
    print("  The user: unzip, double-click Paper2STL.cmd (SmartScreen ->")
    print("  'More info' > 'Run anyway' the first time).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
