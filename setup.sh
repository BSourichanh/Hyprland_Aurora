#!/usr/bin/env bash
# ==============================================================================
# Script d'Installation & Déploiement Automatisé — Hyprland / Aurora Theme
# Restaure l'environnement complet (dotfiles, hard links, scripts, hyprbar, deps)
# ==============================================================================

set -eo pipefail

# ----------------- COULEURS CHARTE AURORA -----------------
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

# ----------------- LOCALISATION DU PROJET -----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR/dotfiles"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
LOCAL_BIN="$HOME/.local/bin"

if [ ! -d "$DOTFILES_DIR" ]; then
    log_error "Répertoire dotfiles/ introuvable sous $SCRIPT_DIR."
    exit 1
fi

# ----------------- PARSING DES ARGUMENTS -----------------
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
            echo -e "Usage : ./setup.sh [OPTIONS]"
            echo
            echo "Options :"
            echo "  --no-deps       Saute l'installation des paquets système (ne fait que le setup dotfiles)"
            echo "  --force-backup  Force la création d'une archive de sauvegarde de ~/.config/"
            echo "  -h, --help      Affiche cette aide"
            exit 0
            ;;
    esac
done

echo -e "${COLOR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo -e "${BOLD}${COLOR_CYAN}    🌌 DÉPLOIEMENT DU SYSTÈME HYPRLAND / THÈME AURORA 🌌    ${COLOR_RESET}"
echo -e "${COLOR_BLUE}          Architecture Multi-Écrans & Hard Links Inodes        ${COLOR_RESET}"
echo -e "${COLOR_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
echo

# ----------------- ÉTAPE 1 : DÉPENDANCES SYSTÈME -----------------
log_info "1. Vérification et installation des dépendances système..."

SYSTEM_PKGS=(
    waybar
    wofi
    kitty
    hyprlock
    hypridle
    swaybg
    slurp
    grim
    wl-clipboard
    playerctl
    pavucontrol
    jq
    wireplumber
    x11-xserver-utils
    libnotify-bin
    python3
    python3-gi
    python3-dbus
    python3-pil
    fonts-noto
    fonts-font-awesome
)

if [ "$INSTALL_DEPS" -eq 1 ]; then
    if command -v apt-get >/dev/null 2>&1; then
        log_step "Gestionnaire apt détecté (Ubuntu / Debian). Mise à jour des paquets..."
        MISSING_PKGS=()
        for pkg in "${SYSTEM_PKGS[@]}"; do
            if ! dpkg -s "$pkg" >/dev/null 2>&1; then
                MISSING_PKGS+=("$pkg")
            fi
        done

        if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
            log_step "Installation des paquets manquants : ${MISSING_PKGS[*]}"
            sudo apt-get update
            sudo apt-get install -y "${MISSING_PKGS[@]}"
        else
            log_success "Tous les paquets système nécessaires sont déjà installés."
        fi
    elif command -v pacman >/dev/null 2>&1; then
        log_step "Gestionnaire pacman détecté (Arch Linux). Installation..."
        sudo pacman -S --needed --noconfirm \
            waybar wofi kitty hyprlock hypridle swaybg slurp grim \
            wl-clipboard playerctl pavucontrol jq wireplumber xorg-xrandr \
            libnotify python python-gobject python-dbus python-pillow \
            noto-fonts ttf-font-awesome || true
    else
        log_warn "Gestionnaire de paquets inconnu. Veuillez vérifier que les utilitaires Wayland sont présents."
    fi
else
    log_step "Option --no-deps activée : saut de l'étape des paquets système."
fi

# Vérification optionnelle de linux-wallpaperengine
if command -v linux-wallpaperengine >/dev/null 2>&1; then
    log_success "linux-wallpaperengine est installé et disponible dans le PATH."
else
    log_warn "linux-wallpaperengine n'est pas détecté. Le fond d'écran statique swaybg fonctionnera en secours immédiat."
    log_step "Pour installer linux-wallpaperengine : https://github.com/Almamu/linux-wallpaperengine"
fi

# ----------------- ÉTAPE 2 : SAUVEGARDE PRÉVENTIVE -----------------
log_info "2. Sauvegarde des configurations existantes dans ~/.config/..."

BACKUP_DIR="$HOME/.config/aurora_backup_$(date +'%Y%m%d_%H%M%S')"
NEED_BACKUP=0

TARGET_DIRS=("hypr" "waybar" "wofi" "kitty")
for d in "${TARGET_DIRS[@]}"; do
    TARGET_PATH="$CONFIG_DIR/$d"
    if [ -d "$TARGET_PATH" ]; then
        NEED_BACKUP=1
        break
    fi
done

if [ "$NEED_BACKUP" -eq 1 ] || [ "$FORCE_BACKUP" -eq 1 ]; then
    mkdir -p "$BACKUP_DIR"
    for d in "${TARGET_DIRS[@]}"; do
        if [ -d "$CONFIG_DIR/$d" ]; then
            log_step "Archivage de ~/.config/$d vers $BACKUP_DIR/$d..."
            cp -r --preserve=all "$CONFIG_DIR/$d" "$BACKUP_DIR/" 2>/dev/null || true
        fi
    done
    log_success "Sauvegarde créée dans : $BACKUP_DIR"
else
    log_step "Aucune configuration conflictuelle à sauvegarder."
fi

# ----------------- ÉTAPE 3 : CRÉATION DES HARD LINKS -----------------
log_info "3. Déploiement des Hard Links (conformité charte Aurora)..."

mkdir -p "$CONFIG_DIR"
TOTAL_LINKS=0

while IFS= read -r -d '' src_file; do
    rel_path="${src_file#$DOTFILES_DIR/}"
    dst_file="$CONFIG_DIR/$rel_path"
    mkdir -p "$(dirname "$dst_file")"

    # Vérifier si un fichier existe déjà
    if [ -e "$dst_file" ]; then
        # Si c'est déjà le même inode, rien à faire
        if [ "$(stat -c %i "$src_file")" = "$(stat -c %i "$dst_file")" ]; then
            TOTAL_LINKS=$((TOTAL_LINKS + 1))
            continue
        fi
        rm -f "$dst_file"
    fi

    # Créer le lien physique (hard link)
    ln "$src_file" "$dst_file"
    TOTAL_LINKS=$((TOTAL_LINKS + 1))
done < <(find "$DOTFILES_DIR" -type f -not -name "*.bak" -not -name "*-bak" -not -name "*.pyc" -print0)

log_success "$TOTAL_LINKS hard links établis entre dotfiles/ et ~/.config/."

# ----------------- ÉTAPE 4 : PERMISSIONS D'EXÉCUTION -----------------
log_info "4. Attribution des droits d'exécution sur les scripts..."

chmod +x "$DOTFILES_DIR"/hypr/lock.sh 2>/dev/null || true
chmod +x "$DOTFILES_DIR"/hypr/scripts/*.sh 2>/dev/null || true
chmod +x "$DOTFILES_DIR"/hypr/scripts/*.py 2>/dev/null || true
chmod +x "$DOTFILES_DIR"/waybar/scripts/*.py 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/scripts/*.py 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/scripts/hyprbar 2>/dev/null || true
log_success "Permissions appliquées."

# ----------------- ÉTAPE 5 : INSTALLATION DE HYPRBAR -----------------
log_info "5. Installation de la commande CLI 'hyprbar'..."

mkdir -p "$LOCAL_BIN"
if [ -f "$SCRIPT_DIR/scripts/hyprbar" ]; then
    cp "$SCRIPT_DIR/scripts/hyprbar" "$LOCAL_BIN/hyprbar"
    chmod +x "$LOCAL_BIN/hyprbar"
    log_success "Utilitaire 'hyprbar' installé dans $LOCAL_BIN/hyprbar."
fi

# Vérification du PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    log_warn "$HOME/.local/bin n'est pas encore présent dans votre PATH."
    log_step "Ajoutez 'export PATH=\"\$HOME/.local/bin:\$PATH\"' à votre ~/.bashrc ou ~/.zshrc."
fi

# ----------------- ÉTAPE 6 : DOSSIERS SYSTÈME & CACHES -----------------
log_info "6. Initialisation des répertoires multimédia et caches..."

mkdir -p "${XDG_PICTURES_DIR:-$HOME/Images}/Captures d’écran"
mkdir -p "/tmp/spotify_card_cache"

# Synchronisation optionnelle des shaders Steam Workshop si présent
WORKSHOP_DIR="$HOME/.steam/steam/steamapps/workshop/content/431960/3566437475"
if [ -d "$WORKSHOP_DIR" ]; then
    log_step "Dossier Steam Workshop Lucy détecté. Synchronisation des shaders..."
    python3 "$SCRIPT_DIR/scripts/wallpaper_tool.py" sync 2>/dev/null || true
    log_success "Shaders et masques synchronisés vers Steam Workshop."
fi

# ----------------- ÉTAPE 7 : SERVICES SYSTEMD UTILISATEUR -----------------
log_info "7. Configuration de l'agent d'authentification Polkit..."

if systemctl --user list-unit-files hyprpolkitagent.service >/dev/null 2>&1; then
    systemctl --user enable --now hyprpolkitagent.service 2>/dev/null || true
    log_success "Service hyprpolkitagent.service activé pour la session utilisateur."
else
    log_step "hyprpolkitagent sera démarré automatiquement via hyprland.conf (exec-once)."
fi

# ----------------- ÉTAPE 8 : AUDIT D'INTÉGRITÉ FINAL -----------------
log_info "8. Exécution de l'audit final d'intégrité..."

if python3 "$SCRIPT_DIR/scripts/wallpaper_tool.py" check-links; then
    echo
    echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo -e "${BOLD}${COLOR_GREEN}    🎉 INSTALLATION ET CONFIGURATION AURORA TERMINÉES ! 🎉    ${COLOR_RESET}"
    echo -e "${COLOR_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${COLOR_RESET}"
    echo
    echo -e "Pour démarrer ou appliquer votre nouvel environnement :"
    echo -e "  • ${BOLD}Depuis un TTY${COLOR_RESET} : Lancez ${COLOR_CYAN}Hyprland${COLOR_RESET}"
    echo -e "  • ${BOLD}Session déjà active${COLOR_RESET} : Lancez ${COLOR_CYAN}hyprctl reload && hyprbar restart${COLOR_RESET}"
    echo -e "  • ${BOLD}Piloter Waybar & Spotify${COLOR_RESET} : Utilisez la commande ${COLOR_CYAN}hyprbar${COLOR_RESET}"
    echo
else
    log_error "L'audit des hard links a détecté des anomalies. Veuillez vérifier les permissions."
    exit 1
fi
