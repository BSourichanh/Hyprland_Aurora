#!/usr/bin/env bash
# ==============================================================================
# Script d'Installation & Déploiement Automatisé — Hyprland / Thème Aurora
# Orchestrateur modulaire : packages, compilations, hardlinks stricts et audits.
# ==============================================================================

set -eo pipefail

COLOR_CYAN="\033[38;2;0;240;255m"
COLOR_BLUE="\033[38;2;122;162;247m"
COLOR_PURPLE="\033[38;2;151;120;208m"
COLOR_GREEN="\033[38;2;115;218;202m"
COLOR_RED="\033[38;2;247;118;142m"
COLOR_RESET="\033[0m"
BOLD="\033[1m"

log_info()    { echo -e "${COLOR_BLUE}==>${COLOR_RESET} ${BOLD}$*${COLOR_RESET}"; }
log_step()    { echo -e "${COLOR_CYAN}  ->${COLOR_RESET} $*"; }
log_success() { echo -e "${COLOR_GREEN}  ✓${COLOR_RESET} ${BOLD}$*${COLOR_RESET}"; }
log_warn()    { echo -e "${COLOR_PURPLE}  !${COLOR_RESET} ${BOLD}$*${COLOR_RESET}"; }
log_error()   { echo -e "${COLOR_RED}  ✗ ERREUR :${COLOR_RESET} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR/dotfiles"
LOCAL_BIN="$HOME/.local/bin"

if [ ! -d "$DOTFILES_DIR" ]; then
    log_error "Répertoire dotfiles/ introuvable sous $SCRIPT_DIR."
    exit 1
fi

INSTALL_DEPS=1
FORCE_BACKUP=0

for arg in "$@"; do
    case "$arg" in
        --no-deps)
            INSTALL_DEPS=0
            ;;
        --force-backup)
            FORCE_BACKUP=1
            ;;
        -h|--help)
            echo -e "${COLOR_CYAN}Installation & Configuration Aurora Hyprland${COLOR_RESET}"
            echo "Usage : ./setup.sh [OPTIONS]"
            echo
            echo "Options :"
            echo "  --no-deps       Saute l'installation des paquets système"
            echo "  --force-backup  Force l'archivage préventif de ~/.config/"
            echo "  -h, --help      Affiche cette aide"
            exit 0
            ;;
        *)
            log_error "Option inconnue : $arg (utilisez --help)."
            exit 1
            ;;
    esac
done

echo -e "${COLOR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "${BOLD}${COLOR_CYAN}    🌌 DÉPLOIEMENT DU SYSTÈME HYPRLAND / THÈME AURORA 🌌    ${COLOR_RESET}"
echo -e "${COLOR_BLUE}          Architecture Multi-Écrans & Hard Links Inodes        ${COLOR_RESET}"
echo -e "${COLOR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo

# 1. Dépendances système et intégration Nautilus
if [ "$INSTALL_DEPS" -eq 1 ]; then
    bash "$SCRIPT_DIR/scripts/setup/packages.sh"
else
    log_step "Option --no-deps activée : saut des paquets système."
    bash "$SCRIPT_DIR/scripts/setup/packages.sh" --nautilus-only
fi

# 2. Compilation et patchs ergonomiques
bash "$SCRIPT_DIR/scripts/setup/compile.sh"

# 3. Remplacement des symlinks de dossiers & déploiement des vrais hard links
bash "$SCRIPT_DIR/scripts/setup/hardlinks.sh" "$FORCE_BACKUP"

# 4. Permissions d'exécution & Hook Git pre-commit
log_info "5. Attribution des droits d'exécution et installation du hook Git..."
chmod +x "$SCRIPT_DIR/setup.sh" "$SCRIPT_DIR/hooks/pre-commit" 2>/dev/null || true
chmod +x "$DOTFILES_DIR"/hypr/lock.sh 2>/dev/null || true
chmod +x "$DOTFILES_DIR"/hypr/scripts/*.sh "$DOTFILES_DIR"/hypr/scripts/*.py 2>/dev/null || true
chmod +x "$DOTFILES_DIR"/waybar/scripts/*.py "$DOTFILES_DIR"/swaync/scripts/*.py 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/scripts/*.py "$SCRIPT_DIR"/scripts/hyprbar "$SCRIPT_DIR"/scripts/verify_aurora.sh 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/scripts/setup/*.sh 2>/dev/null || true

if [ -d "$SCRIPT_DIR/.git" ] && [ -f "$SCRIPT_DIR/hooks/pre-commit" ]; then
    mkdir -p "$SCRIPT_DIR/.git/hooks"
    ln -sf "../../hooks/pre-commit" "$SCRIPT_DIR/.git/hooks/pre-commit"
    log_success "Hook Git pre-commit lié (.git/hooks/pre-commit -> ../../hooks/pre-commit)."
fi
log_success "Permissions appliquées."

# 5. Outils CLI locaux
log_info "6. Installation des utilitaires CLI dans ~/.local/bin..."
mkdir -p "$LOCAL_BIN"
if [ -f "$SCRIPT_DIR/scripts/hyprbar" ]; then
    if [ "$(stat -c %d "$SCRIPT_DIR/scripts/hyprbar")" = "$(stat -c %d "$LOCAL_BIN")" ]; then
        ln -f "$SCRIPT_DIR/scripts/hyprbar" "$LOCAL_BIN/hyprbar"
        log_success "Utilitaire 'hyprbar' déployé par hardlink dans $LOCAL_BIN/hyprbar."
    else
        ln -sf "$SCRIPT_DIR/scripts/hyprbar" "$LOCAL_BIN/hyprbar"
        log_success "Utilitaire 'hyprbar' déployé par symlink dans $LOCAL_BIN/hyprbar."
    fi
fi

if [ -f "$SCRIPT_DIR/scripts/aurora_mcp_server.py" ]; then
    cat > "$LOCAL_BIN/aurora-mcp" << EOF
#!/usr/bin/env bash
export PATH="\$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:\$PATH"
export PYTHONDONTWRITEBYTECODE=1
PROJECT_DIR="${SCRIPT_DIR}"
if [ ! -f "\$PROJECT_DIR/scripts/aurora_mcp_server.py" ]; then
    PROJECT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/../../Documents/antigravity/hyprland_project" 2>/dev/null && pwd || echo "\$HOME/Documents/antigravity/hyprland_project")"
fi
exec uv run --with "mcp<2" --with pillow python3 -B "\$PROJECT_DIR/scripts/aurora_mcp_server.py" "\$@"
EOF
    chmod +x "$LOCAL_BIN/aurora-mcp"
    log_success "Serveur 'aurora-mcp' configuré dans $LOCAL_BIN/aurora-mcp (portable + Pillow)."
fi

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    log_warn "$HOME/.local/bin n'est pas encore présent dans votre PATH."
fi

# 6. Dossiers système & caches (masque régénéré uniquement si absent ou obsolète)
log_info "7. Initialisation des répertoires multimédia et caches..."
AURORA_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora"
mkdir -p -m 700 "$AURORA_RUNTIME_DIR" "$AURORA_RUNTIME_DIR/spotify_covers"
mkdir -p "${XDG_PICTURES_DIR:-$HOME/Images}/Captures d’écran"

MASK_FILE="$SCRIPT_DIR/ressource/blackwall/blackwall_mask.png"
if [ ! -f "$MASK_FILE" ] || \
   [ "$SCRIPT_DIR/ressource/lucy.png" -nt "$MASK_FILE" ] || \
   [ "$SCRIPT_DIR/ressource/shake_flowmask.png" -nt "$MASK_FILE" ] || \
   [ "$SCRIPT_DIR/ressource/waterwaves_mask.png" -nt "$MASK_FILE" ]; then
    PYTHONDONTWRITEBYTECODE=1 python3 -B "$SCRIPT_DIR/scripts/wallpaper_tool.py" mask
else
    log_step "Masque Blackwall déjà à jour ($MASK_FILE)."
fi
log_success "Masques Blackwall et Lucy validés."

# 7. Agent Polkit
if systemctl --user list-unit-files hyprpolkitagent.service >/dev/null 2>&1; then
    systemctl --user enable --now hyprpolkitagent.service 2>/dev/null || true
    log_success "Service hyprpolkitagent.service activé pour la session utilisateur."
fi

# 8. Audit d'intégrité final
log_info "8. Exécution de l'audit final d'intégrité..."
if PYTHONDONTWRITEBYTECODE=1 python3 -B "$SCRIPT_DIR/scripts/wallpaper_tool.py" check-links; then
    echo
    echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo -e "${BOLD}${COLOR_GREEN}    🎉 INSTALLATION ET CONFIGURATION AURORA TERMINÉES ! 🎉    ${COLOR_RESET}"
    echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo
else
    log_error "L'audit des hard links a détecté des anomalies. Veuillez vérifier les permissions."
    exit 1
fi
