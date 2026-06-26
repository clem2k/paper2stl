#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Assemble a lightweight, self-bootstrapping  Paper2STL.app  for macOS.
#
# The resulting .app contains only the Python SOURCE (a few MB) — NOT the heavy
# dependencies. On its FIRST launch it creates a venv INSIDE the bundle
#   Paper2STL.app/Contents/Resources/venv
# and pip-installs the core requirements from PyPI (~400 MB, one time).
# Every launch after that starts the GUI instantly and silently.
# Because everything lives inside the .app, it is fully portable: delete the
# bundle and nothing is left behind (no ~/Library, no preferences).
#
# Usage (run on any Mac, no special tools required):
#   ./scripts/build_installer_app.sh
#
# Output:
#   dist/Paper2STL.app   →  zip it and upload to GitHub Releases
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { printf "${CYAN}▶${NC}  %s\n" "$*"; }
ok()   { printf "${GREEN}✓${NC}  %s\n" "$*"; }
warn() { printf "${YELLOW}⚠${NC}  %s\n" "$*"; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

APP="dist/Paper2STL.app"
RES="$APP/Contents/Resources"
MACOS="$APP/Contents/MacOS"

info "Cleaning previous build…"
rm -rf "$APP"
mkdir -p "$MACOS" "$RES/src"

# ── 1. Info.plist ──────────────────────────────────────────────────────────────
info "Writing Info.plist…"
cat > "$APP/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>        <string>Paper2STL</string>
  <key>CFBundleIdentifier</key>        <string>com.paper2stl.app</string>
  <key>CFBundleName</key>              <string>Paper2STL</string>
  <key>CFBundleDisplayName</key>       <string>Paper2STL</string>
  <key>CFBundleIconFile</key>          <string>Paper2STL</string>
  <key>CFBundleVersion</key>           <string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundlePackageType</key>       <string>APPL</string>
  <key>NSHighResolutionCapable</key>   <true/>
  <key>LSMinimumSystemVersion</key>    <string>12.0</string>
  <key>NSHumanReadableCopyright</key>  <string>MIT License</string>
</dict>
</plist>
PLIST

# ── 2. Copy the Python source (exclude caches / tests to stay light) ───────────
info "Bundling source…"
if command -v rsync &>/dev/null; then
    rsync -a --exclude='__pycache__' --exclude='*.pyc' \
        "$REPO/paper2stl" "$RES/src/"
else
    cp -R "$REPO/paper2stl" "$RES/src/"
    find "$RES/src" -name '__pycache__' -type d -prune -exec rm -rf {} +
fi
# pyproject.toml + README.md are required by the build backend; LICENCE for good measure.
cp "$REPO/pyproject.toml" "$RES/src/"
cp "$REPO/README.md"      "$RES/src/" 2>/dev/null || warn "README.md missing — pip build may warn"
cp "$REPO/LICENCE"        "$RES/src/" 2>/dev/null || true
ok "Source bundled ($(du -sh "$RES/src" | cut -f1))"

# ── 2b. App icon (Contents/Resources/Paper2STL.icns) ──────────────────────────
# Built from res/ico.png with native macOS tools (sips + iconutil). Falls back
# gracefully if the source or tools are missing — the app still works.
ICON_SRC="$REPO/res/ico.png"
if [ -f "$ICON_SRC" ] && command -v sips &>/dev/null && command -v iconutil &>/dev/null; then
    info "Generating app icon…"
    ICONSET="$(mktemp -d)/Paper2STL.iconset"
    mkdir -p "$ICONSET"
    for s in 16 32 64 128 256 512 1024; do
        sips -z "$s" "$s" "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png" &>/dev/null || true
    done
    # Retina (@2x) variants expected by iconutil.
    cp "$ICONSET/icon_32x32.png"     "$ICONSET/icon_16x16@2x.png"   2>/dev/null || true
    cp "$ICONSET/icon_64x64.png"     "$ICONSET/icon_32x32@2x.png"   2>/dev/null || true
    cp "$ICONSET/icon_256x256.png"   "$ICONSET/icon_128x128@2x.png" 2>/dev/null || true
    cp "$ICONSET/icon_512x512.png"   "$ICONSET/icon_256x256@2x.png" 2>/dev/null || true
    cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png" 2>/dev/null || true
    rm -f "$ICONSET/icon_64x64.png"                # not a standard iconset slot
    if iconutil -c icns "$ICONSET" -o "$RES/Paper2STL.icns" 2>/dev/null; then
        ok "App icon generated."
    else
        warn "iconutil failed — app will use the default icon."
    fi
    rm -rf "$(dirname "$ICONSET")"
else
    warn "res/ico.png or sips/iconutil missing — app will use the default icon."
fi

# ── 3. Launcher (Contents/MacOS/Paper2STL) ─────────────────────────────────────
# Fast path: venv ready → launch GUI directly (silent, instant).
# First run:  no venv  → open the bootstrap installer in Terminal (visible).
info "Writing launcher…"
cat > "$MACOS/Paper2STL" << 'LAUNCHER'
#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
RES="$(cd "$HERE/../Resources" && pwd)"
VENV="$RES/venv"
MARKER="$VENV/.paper2stl_installed"
export PAPER2STL_PORTABLE_DIR="$RES"

if [ -x "$VENV/bin/python" ] && [ -f "$MARKER" ]; then
    exec "$VENV/bin/python" -m paper2stl.gui
fi

# First launch — run the installer in Terminal so the user sees the progress.
open -a Terminal "$RES/bootstrap.command"
LAUNCHER
chmod +x "$MACOS/Paper2STL"

# ── 4. Bootstrap installer (Contents/Resources/bootstrap.command) ─────────────
info "Writing first-run installer…"
cat > "$RES/bootstrap.command" << 'BOOTSTRAP'
#!/bin/bash
# Paper2STL — premier lancement : installation automatique de l'environnement.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info() { printf "${CYAN}▶${NC}  %s\n" "$*"; }
ok()   { printf "${GREEN}✓${NC}  %s\n" "$*"; }
warn() { printf "${YELLOW}⚠${NC}  %s\n" "$*"; }
die()  { printf "\n${RED}✗  Erreur :${NC} %s\n\nAppuyez sur Entrée pour fermer..." "$*"; read -r; exit 1; }

RES="$(cd "$(dirname "$0")" && pwd)"
SRC="$RES/src"
APP="$(cd "$RES/../.." && pwd)"          # …/Paper2STL.app
SUPPORT="$RES"                            # everything lives inside the bundle
VENV="$RES/venv"
MARKER="$VENV/.paper2stl_installed"

clear
printf "${BOLD}"
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║         Paper2STL — Première installation        ║"
echo "  ╚═══════════════════════════════════════════════════╝"
printf "${NC}\n"
echo "  Cette étape n'a lieu qu'UNE seule fois."
echo "  Les prochains lancements seront instantanés."
echo ""

# ── find Python 3.10+ ───────────────────────────────────────────────────────
info "Recherche de Python 3.10 ou plus récent…"
PYTHON=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" &>/dev/null && \
       "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null; then
        PYTHON="$(command -v "$c")"
        ok "Trouvé : $("$c" --version 2>&1)"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    warn "Python 3.10+ introuvable."
    echo "   ➜  Installez Python depuis https://www.python.org/downloads/macos/"
    echo "      puis relancez Paper2STL."
    open "https://www.python.org/downloads/macos/" 2>/dev/null || true
    die "Python 3.10+ requis."
fi
echo ""

# ── venv + install (robuste) ────────────────────────────────────────────────
mkdir -p "$SUPPORT"

# Verrou anti-double-lancement : deux bootstraps simultanés corrompraient le
# venv. Auto-réparant : on vole le verrou si le processus qui le détient est mort.
LOCK="$SUPPORT/.install.lock"
if [ -d "$LOCK" ]; then
    oldpid="$(cat "$LOCK/pid" 2>/dev/null || true)"
    if [ -n "$oldpid" ] && kill -0 "$oldpid" 2>/dev/null; then
        warn "Une installation est déjà en cours (fenêtre PID $oldpid)."
        echo "   Fermez les autres fenêtres Terminal, puis relancez si besoin."
        sleep 4; exit 0
    fi
    rm -rf "$LOCK"                       # verrou périmé (processus mort)
fi
mkdir -p "$LOCK"; echo "$$" > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

PYBIN="$VENV/bin/python"
# Un venv n'est valide que si python ET le module pip répondent.
venv_ok() { [ -x "$PYBIN" ] && "$PYBIN" -m pip --version >/dev/null 2>&1; }

if ! venv_ok; then
    info "Création de l'environnement…"
    rm -rf "$VENV"                       # repart de zéro si absent ou incomplet
    "$PYTHON" -m venv "$VENV" || die "Création de l'environnement impossible ($PYTHON)."
    # Garantit pip dans le venv (au cas où venv ne l'aurait pas posé).
    "$PYBIN" -m pip --version >/dev/null 2>&1 \
        || "$PYBIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
    if ! "$PYBIN" -m pip --version >/dev/null 2>&1; then
        warn "pip absent — récupération de get-pip.py…"
        curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$SUPPORT/get-pip.py" \
            && "$PYBIN" "$SUPPORT/get-pip.py" >/dev/null 2>&1 || true
    fi
    venv_ok || die "Impossible d'installer pip dans l'environnement."
fi

info "Mise à jour de pip…"
"$PYBIN" -m pip install --quiet --upgrade pip

echo ""
info "Installation des dépendances (~400 Mo, une seule fois)…"
printf "   ${YELLOW}Patientez — PySide6, OpenCV, NumPy se téléchargent.${NC}\n\n"
"$PYBIN" -m pip install "$SRC" || die "Échec de l'installation des dépendances."

touch "$MARKER"
echo ""
ok "Installation terminée."
echo ""

# ── launch the app via its normal fast path ─────────────────────────────────
info "Lancement de Paper2STL…"
open "$APP"

echo ""
echo "  Vous pouvez fermer cette fenêtre."
sleep 2
exit 0
BOOTSTRAP
chmod +x "$RES/bootstrap.command"

# ── 5. Ad-hoc signature (reduces Gatekeeper friction) ─────────────────────────
info "Ad-hoc signing…"
codesign --force --deep --sign - "$APP" 2>/dev/null \
    && ok "Signed (ad-hoc)" \
    || warn "codesign unavailable — app still works (right-click ▸ Open on first run)"

# ── done ──────────────────────────────────────────────────────────────────────
echo ""
ok "Built  $APP  ($(du -sh "$APP" | cut -f1))"
echo ""
echo "  Distribuer :"
echo "    cd dist && zip -r -y Paper2STL-mac.zip Paper2STL.app"
echo "    → uploader Paper2STL-mac.zip sur GitHub Releases"
echo ""
echo "  L'utilisateur : décompresse, clic-droit sur Paper2STL.app ▸ Ouvrir."
