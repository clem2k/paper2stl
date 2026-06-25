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
SUPPORT="$HOME/Library/Application Support/Paper2STL"
VENV="$SUPPORT/venv"
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
