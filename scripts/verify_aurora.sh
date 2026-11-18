#!/usr/bin/env bash
# ==============================================================================
# verify_aurora.sh — Unified Proof & Zero-Regression Verification Script
# Hyprland Aurora Environment
#
# Usage: ./scripts/verify_aurora.sh [--read-only]
# Runs:
# 1. tests/test_audit_dotfiles_syntax.py
# 2. tests/test_audit_hardlinks.py
# 3. tests/test_audit_aurora_conformity.py
# 4. ~/.local/bin/aurora-mcp reload (skipped when --read-only)
# 5. Volumetric audit (< 500 lines strict, warning >= 400 lines)
# 6. C99 dry compilation & link check in /tmp
# 7. tests/audit_multimedia_performance.py
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1

READ_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --read-only)
            READ_ONLY=1
            ;;
        -h|--help)
            echo "Usage: ./scripts/verify_aurora.sh [--read-only]"
            exit 0
            ;;
        *)
            echo "Option inconnue : $arg" >&2
            exit 1
            ;;
    esac
done

COLOR_CYAN="\033[38;2;0;240;255m"
COLOR_BLUE="\033[38;2;122;162;247m"
COLOR_GREEN="\033[38;2;115;218;202m"
COLOR_PURPLE="\033[38;2;151;120;208m"
COLOR_RED="\033[38;2;247;118;142m"
COLOR_RESET="\033[0m"
BOLD="\033[1m"

step_banner() {
    echo -e "\n${COLOR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo -e "${BOLD}${COLOR_BLUE}▶ ÉTAPE $1 : $2${COLOR_RESET}"
    echo -e "${COLOR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
}

fail_exit() {
    echo -e "\n${BOLD}${COLOR_RED}✗ ÉCHEC DU TEST : $1${COLOR_RESET}" >&2
    exit 1
}

echo -e "${BOLD}${COLOR_CYAN}============================================================${COLOR_RESET}"
echo -e "${BOLD}${COLOR_CYAN}   🌌 SCRIPT DE PREUVES UNIFIÉ & VALIDATION ZÉRO-RÉGRESSION 🌌   ${COLOR_RESET}"
echo -e "${BOLD}${COLOR_BLUE}       Architecture Multi-Écrans Hyprland / Thème Aurora       ${COLOR_RESET}"
echo -e "${BOLD}${COLOR_CYAN}============================================================${COLOR_RESET}"

# ----------------- 1. AUDIT SYNTAXIQUE DES DOTFILES -----------------
step_banner "1" "Audit syntaxique et statique des dotfiles"
python3 -B "$PROJECT_ROOT/tests/test_audit_dotfiles_syntax.py" || fail_exit "test_audit_dotfiles_syntax.py"

# ----------------- 2. AUDIT PHYSIQUE DES HARD LINKS -----------------
step_banner "2" "Contrôle physique des hard links et intégrité des inodes"
python3 -B "$PROJECT_ROOT/tests/test_audit_hardlinks.py" || fail_exit "test_audit_hardlinks.py"

# ----------------- 3. CONFORMITÉ CHARTE AURORA -----------------
step_banner "3" "Vérification stricte de la charte Aurora (4 piliers)"
python3 -B "$PROJECT_ROOT/tests/test_audit_aurora_conformity.py" || fail_exit "test_audit_aurora_conformity.py"

# ----------------- 4. RECHARGEMENT RUNTIME AURORA-MCP -----------------
step_banner "4" "Rechargement complet runtime via aurora-mcp reload"
if [ "$READ_ONLY" -eq 1 ]; then
    echo -e "${COLOR_PURPLE}ℹ Mode --read-only actif : étape aurora-mcp reload (mutante) ignorée.${COLOR_RESET}"
else
    AURORA_MCP_BIN="$HOME/.local/bin/aurora-mcp"
    if [ ! -x "$AURORA_MCP_BIN" ]; then
        fail_exit "Binaire $AURORA_MCP_BIN introuvable ou non exécutable"
    fi
    MCP_OUTPUT=$("$AURORA_MCP_BIN" reload)
    echo "$MCP_OUTPUT"
    if ! echo "$MCP_OUTPUT" | grep -q '"ok": true'; then
        fail_exit "aurora-mcp reload a échoué"
    fi
fi

# ----------------- 5. CONTRÔLE VOLUMÉTRIQUE (< 500 LIGNES) -----------------
step_banner "5" "Contrôle volumétrique (< 500 lignes strict, alerte >= 400)"

AURORA_PROJECT_ROOT="$PROJECT_ROOT" python3 -B - << 'EOF'
import os
import sys
from pathlib import Path

root = Path(os.environ["AURORA_PROJECT_ROOT"])
targets = [root / "dotfiles", root / "scripts", root / "tests", root / "src", root / "hooks"]
over = []
warn = []
checked = 0

setup_sh = root / "setup.sh"
if setup_sh.exists():
    with open(setup_sh, "r", encoding="utf-8", errors="ignore") as f:
        cnt = sum(1 for _ in f)
    checked += 1
    if cnt >= 500:
        over.append(("setup.sh", cnt))
    elif cnt >= 400:
        warn.append(("setup.sh", cnt))

for target in targets:
    if not target.exists():
        continue
    for p in target.rglob("*"):
        if not p.is_file():
            continue
        if any(part in [".git", "__pycache__"] for part in p.parts):
            continue
        if p.suffix in [".so", ".jpg", ".png", ".patch", ".lock", ".pyc", ".gif", ".o", ".tex"]:
            continue
        if p.name in ["aurora-wallpaper", "stb_image.h", "xdg-shell-client-protocol.h", "wlr-layer-shell-unstable-v1-client-protocol.h"]:
            continue
        with open(p, "rb") as f:
            chunk = f.read(1024)
            if b"\0" in chunk:
                continue
        with open(p, "r", encoding="utf-8", errors="ignore") as fp:
            count = sum(1 for _ in fp)
        checked += 1
        rel = str(p.relative_to(root))
        if count >= 500:
            over.append((rel, count))
        elif count >= 400:
            warn.append((rel, count))

print(f"Fichiers internes vérifiés : {checked}")
if warn:
    print("⚠ Fichiers approchant le plafond (>= 400 lignes) :")
    for fname, count in warn:
        print(f"  - {fname}: {count} lignes")
if over:
    print("✗ Fichiers atteignant ou dépassant le plafond strict (>= 500 lignes) :")
    for fname, count in over:
        print(f"  - {fname}: {count} lignes")
    sys.exit(1)

print("✓ 100% des fichiers internes respectent le plafond strict < 500 lignes (CONTRAT-RUNTIME.md).")
EOF

# ----------------- 6. COMPILATION C99 À SEC DANS /TMP -----------------
step_banner "6" "Vérification compilation C99 à sec (aurora-wallpaper -> /tmp)"
C99_TMP="$(mktemp -d /tmp/aurora_verify_c99_XXXXXX)"
cleanup_c99() {
    rm -rf "$C99_TMP"
}
trap cleanup_c99 EXIT

SRC_DIR="$PROJECT_ROOT/src/aurora_wallpaper"
gcc -std=c99 -O2 -Wall -Wextra -c "$SRC_DIR/main.c" -o "$C99_TMP/main.o" || fail_exit "Compilation main.c"
gcc -std=c99 -O2 -Wall -Wextra -c "$SRC_DIR/gl_utils.c" -o "$C99_TMP/gl_utils.o" || fail_exit "Compilation gl_utils.c"
gcc -std=c99 -O2 -Wall -Wextra -c "$SRC_DIR/wlr-layer-shell-unstable-v1-protocol.c" -o "$C99_TMP/wlr.o" || fail_exit "Compilation wlr-layer-shell"
gcc -std=c99 -O2 -Wall -Wextra -c "$SRC_DIR/xdg-shell-protocol.c" -o "$C99_TMP/xdg.o" || fail_exit "Compilation xdg-shell"
gcc -std=c99 -O2 -Wall -Wextra "$C99_TMP"/*.o -lwayland-client -lwayland-egl -lEGL -lGLESv2 -lm -o "$C99_TMP/aurora-wallpaper" || fail_exit "Édition de lien aurora-wallpaper"
echo "✓ Compilation et édition de lien C99 validées dans $C99_TMP (nettoyage automatique)."

# ----------------- 7. AUDIT PERFORMANCE MULTIMÉDIA -----------------
step_banner "7" "Audit performance Waybar GPU, Spotify IPC et utilitaires"
python3 -B "$PROJECT_ROOT/tests/audit_multimedia_performance.py" || fail_exit "audit_multimedia_performance.py"

# ----------------- 8. TESTS FONCTIONNELS RENFORCÉS -----------------
step_banner "8" "Tests fonctionnels renforcés (lock policy P1, autocompact C99, MCP, thème)"
python3 -B -m unittest discover -s "$PROJECT_ROOT/tests" -p "test_functional_*.py" -v || fail_exit "test_functional_*.py"

# ----------------- VALIDATION FINALE -----------------
echo -e "\n${BOLD}${COLOR_GREEN}============================================================${COLOR_RESET}"
echo -e "${BOLD}${COLOR_GREEN}   ✓ TOUTES LES VÉRIFICATIONS ONT RÉUSSI (100% CONFORME)   ${COLOR_RESET}"
echo -e "${BOLD}${COLOR_GREEN}   VALIDATION FINALE ZÉRO-RÉGRESSION TERMINÉE AVEC SUCCÈS   ${COLOR_RESET}"
echo -e "${BOLD}${COLOR_GREEN}============================================================${COLOR_RESET}"

exit 0
