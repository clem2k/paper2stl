#requires -Version 5
<#
  Assemble a lightweight, self-bootstrapping Paper2STL app for Windows.
  This is the exact analogue of scripts/build_installer_app.sh (macOS).

  The output contains only the Python SOURCE (a few MB) -- NOT the heavy
  dependencies. On its FIRST launch it creates a venv INSIDE the app folder
      dist\Paper2STL\venv
  and pip-installs the core requirements from PyPI (~400 MB, one time).
  Every launch after that starts the GUI instantly. Because everything lives
  next to Paper2STL.cmd, the app is fully portable: delete the folder and
  nothing is left behind (no %LOCALAPPDATA%, no registry).

  Run on Windows (no special tools required):
      powershell -ExecutionPolicy Bypass -File scripts\build_installer_app.ps1

  Output:
      dist\Paper2STL\              the app folder (double-click Paper2STL.cmd)
      dist\Paper2STL-windows.zip   ready to attach to a GitHub Release

  NOTE: this script must be run on Windows; it cannot be executed from macOS.
#>
$ErrorActionPreference = 'Stop'

function Info($m) { Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "OK $m" -ForegroundColor Green }
function Warn($m) { Write-Host " ! $m" -ForegroundColor Yellow }

$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$App = Join-Path $Repo 'dist\Paper2STL'
$Res = Join-Path $App 'resources'
$Src = Join-Path $Res 'src'

# -- clean ---------------------------------------------------------------------
Info 'Cleaning previous build...'
if (Test-Path $App) {
    try {
        Remove-Item -Recurse -Force $App -ErrorAction Stop
    } catch {
        Write-Host ""
        Write-Host "ERROR: cannot clean the previous build - a file is locked:" -ForegroundColor Red
        Write-Host "   $App" -ForegroundColor Red
        Write-Host ""
        Write-Host "This usually means a Paper2STL instance is still RUNNING from that" -ForegroundColor Yellow
        Write-Host "folder (its venv pythonw.exe holds it open). Close the app/GUI, then" -ForegroundColor Yellow
        Write-Host "run the build again. Aborted on purpose so no stale package is shipped." -ForegroundColor Yellow
        exit 1
    }
}
New-Item -ItemType Directory -Force -Path $Src | Out-Null

# -- 1. bundle source (exclude caches / tests to stay light) -------------------
Info 'Bundling source...'
# robocopy returns 0-7 on success (1 = files copied); do not treat as error.
robocopy (Join-Path $Repo 'paper2stl') (Join-Path $Src 'paper2stl') /E `
    /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
Copy-Item (Join-Path $Repo 'pyproject.toml') $Src
Copy-Item (Join-Path $Repo 'README.md') $Src -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Repo 'LICENCE')   $Src -ErrorAction SilentlyContinue
Ok 'Source bundled'

# -- 2. launcher (Paper2STL.cmd) ----------------------------------------------
# Fast path: venv ready -> launch the GUI with pythonw (no console window).
# First run:  no venv  -> run the bootstrap installer in a visible console.
Info 'Writing launcher...'
$launcher = @'
@echo off
setlocal
set "APPDIR=%~dp0"
set "LNK=%APPDIR%Paper2STL.lnk"
rem First launch: create a portable shortcut (with icon) next to this file.
if not exist "%LNK%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ws=New-Object -ComObject WScript.Shell;" ^
      "$lnk=$ws.CreateShortcut('%APPDIR%Paper2STL.lnk');" ^
      "$lnk.TargetPath='%APPDIR%Paper2STL.cmd';" ^
      "$lnk.WorkingDirectory='%APPDIR%';" ^
      "$ico='%APPDIR%resources\ico.ico'; if (Test-Path $ico) { $lnk.IconLocation=$ico + ',0' }" ^
      "$lnk.Save()" >nul 2>&1
)
set "VENV=%APPDIR%venv"
set "MARKER=%VENV%\.paper2stl_installed"
set "PAPER2STL_PORTABLE_DIR=%APPDIR%"
if exist "%VENV%\Scripts\pythonw.exe" if exist "%MARKER%" (
    start "" "%VENV%\Scripts\pythonw.exe" -m paper2stl.gui
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0resources\bootstrap.ps1"
'@
Set-Content -Path (Join-Path $App 'Paper2STL.cmd') -Value $launcher -Encoding ASCII

# -- 3. first-run installer (resources\bootstrap.ps1) -------------------------
Info 'Writing first-run installer...'
$bootstrap = @'
# Paper2STL - first launch: automatic environment setup.
$ErrorActionPreference = 'Stop'
function Info($m) { Write-Host ">> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "OK $m" -ForegroundColor Green }
function Warn($m) { Write-Host " ! $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host ""; Write-Host "ERROR: $m" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

$Res     = Split-Path -Parent $MyInvocation.MyCommand.Path
$SrcDir  = Join-Path $Res 'src'
$Support = Split-Path -Parent $Res          # the app folder (portable)
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

    Info "Launching Paper2STL..."
    $env:PAPER2STL_PORTABLE_DIR = $Support
    Start-Process $VPyw -ArgumentList '-m', 'paper2stl.gui'
}
finally {
    Remove-Item -Recurse -Force $Lock -ErrorAction SilentlyContinue
}
'@
Set-Content -Path (Join-Path $Res 'bootstrap.ps1') -Value $bootstrap -Encoding UTF8

# -- 3b. bundle icon -----------------------------------------------------------
$icoSrc = Join-Path $Repo 'res\ico.ico'
if (Test-Path $icoSrc) {
    Copy-Item $icoSrc (Join-Path $Res 'ico.ico') -Force
    Ok 'Icon bundled'
} else {
    Warn 'res\ico.ico not found - shortcut will use default icon'
}

# -- 4. zip --------------------------------------------------------------------
Info 'Creating Paper2STL-windows.zip...'
$Zip = Join-Path $Repo 'dist\Paper2STL-windows.zip'
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path $App -DestinationPath $Zip

# -- done ----------------------------------------------------------------------
Write-Host ""
Ok "Built $App"
Write-Host ""
Write-Host "  Distribute:  dist\Paper2STL-windows.zip  -> GitHub Releases"
Write-Host "  The user: unzip, then double-click Paper2STL.cmd (right side: 'More info' >"
Write-Host "  'Run anyway' if SmartScreen prompts the first time)."
