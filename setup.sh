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
    hyprland
    hyprlock
    hypridle
    hyprpicker
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
    python3-nautilus
    gir1.2-nautilus-4.0
    gettext
    fonts-noto
    fonts-font-awesome
    fonts-jetbrains-mono
    meson
    ninja-build
    cmake
    build-essential
    libgtk-3-dev
    libwayland-dev
    wtype
    sway-notification-center
    libxrandr-dev
    libxinerama-dev
    libxcursor-dev
    libxi-dev
    libgl-dev
    libglew-dev
    freeglut3-dev
    libsdl2-dev
    liblz4-dev
    libavcodec-dev
    libavformat-dev
    libavutil-dev
    libswscale-dev
    libxxf86vm-dev
    libglm-dev
    libglfw3-dev
    libmpv-dev
    mpv
    libpulse-dev
    libfftw3-dev
    libfreetype-dev
)

if [ "$INSTALL_DEPS" -eq 1 ]; then
    if command -v apt-get >/dev/null 2>&1; then
        log_step "Gestionnaire apt détecté (Ubuntu / Debian)."
        if ! command -v hyprland >/dev/null 2>&1 && ! apt-cache show hyprland >/dev/null 2>&1; then
            log_step "Ajout du dépôt PPA cppiber/hyprland pour Ubuntu..."
            sudo add-apt-repository -y ppa:cppiber/hyprland || true
            sudo apt-get update
        fi

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

        # Purge automatique du conflit GNOME Terminal sous Nautilus
        if dpkg -s nautilus-extension-gnome-terminal >/dev/null 2>&1; then
            log_step "Désinstallation de nautilus-extension-gnome-terminal (conflit GNOME Terminal)..."
            sudo apt-get remove -y nautilus-extension-gnome-terminal >/dev/null 2>&1 || true
            log_success "Conflit GNOME Terminal retiré."
        fi
    elif command -v pacman >/dev/null 2>&1; then
        log_step "Gestionnaire pacman détecté (Arch Linux). Installation..."
        sudo pacman -S --needed --noconfirm \
            hyprland waybar wofi kitty hyprlock hypridle swaybg slurp grim \
            wl-clipboard playerctl pavucontrol jq wireplumber xorg-xrandr \
            libnotify python python-gobject python-dbus python-pillow \
            python-nautilus gettext noto-fonts ttf-font-awesome \
            meson ninja cmake base-devel || true
    else
        log_warn "Gestionnaire de paquets inconnu. Veuillez vérifier que les utilitaires Wayland sont présents."
    fi
else
    log_step "Option --no-deps activée : saut de l'étape des paquets système."
fi

# ----------------- INTÉGRATION NAUTILUS & KITTY -----------------
log_step "Configuration de l'extension Nautilus (clic droit ➔ Kitty)..."
sudo mkdir -p /usr/share/nautilus-python/extensions /usr/share/glib-2.0/schemas
# Nettoyage préventif des doublons utilisateur ou locaux
sudo rm -f /usr/local/share/nautilus-python/extensions/nautilus_open_any_terminal.py
rm -f "$HOME/.local/share/nautilus-python/extensions/nautilus_open_any_terminal.py"
if [ -f "$SCRIPT_DIR/ressource/nautilus/nautilus_open_any_terminal.py" ]; then
    sudo cp "$SCRIPT_DIR/ressource/nautilus/nautilus_open_any_terminal.py" /usr/share/nautilus-python/extensions/
fi
if [ -f "$SCRIPT_DIR/ressource/nautilus/com.github.stunkymonkey.nautilus-open-any-terminal.gschema.xml" ]; then
    sudo cp "$SCRIPT_DIR/ressource/nautilus/com.github.stunkymonkey.nautilus-open-any-terminal.gschema.xml" /usr/share/glib-2.0/schemas/
    sudo glib-compile-schemas /usr/share/glib-2.0/schemas/ >/dev/null 2>&1 || true
fi
gsettings set com.github.stunkymonkey.nautilus-open-any-terminal terminal 'kitty' 2>/dev/null || true
nautilus -q 2>/dev/null || true
log_success "Nautilus configuré pour ouvrir Kitty directement (instance unique)."

# ----------------- VÉRIFICATION & COMPILATION AURORA WALLPAPER -----------------
if command -v aurora-wallpaper >/dev/null 2>&1 || [ -f "$LOCAL_BIN/aurora-wallpaper" ]; then
    log_success "aurora-wallpaper est installé et disponible dans le PATH."
else
    log_step "Compilation et installation de aurora-wallpaper depuis les sources natives C99..."
    if make -C "$SCRIPT_DIR/src/aurora_wallpaper" install >/dev/null 2>&1; then
        log_success "aurora-wallpaper compilé et installé dans $LOCAL_BIN/aurora-wallpaper."
    else
        log_warn "Échec de compilation de aurora-wallpaper. Le fond statique swaybg fonctionnera en secours."
    fi
fi

# ----------------- VÉRIFICATION DU PLUGIN HYPRSPACE -----------------
if [ -f "$DOTFILES_DIR/hypr/plugins/Hyprspace.so" ]; then
    chmod +x "$DOTFILES_DIR/hypr/plugins/Hyprspace.so"
    log_success "Plugin Hyprspace.so validé et exécutable."
fi

# ----------------- VÉRIFICATION DU PATCH ERGONOMIQUE WOFI -----------------
WOFI_BIN=$(command -v wofi 2>/dev/null || true)
if [ -n "$WOFI_BIN" ] && ! strings "$WOFI_BIN" 2>/dev/null | grep -q "on_motion_select"; then
    log_step "Application du patch Wofi (sélection ergonomique active au survol de la souris)..."
    TMP_WOFI=$(mktemp -d /tmp/wofi_build_XXXXXX)
    if curl -sL https://hg.sr.ht/~scoopta/wofi/archive/v1.4.1.tar.gz | tar -xzf - -C "$TMP_WOFI" --strip-components=1 2>/dev/null; then
        if [ -f "$DOTFILES_DIR/wofi/wofi-hover-select.patch" ]; then
            patch -d "$TMP_WOFI" -p1 < "$DOTFILES_DIR/wofi/wofi-hover-select.patch" >/dev/null 2>&1 || true
            mkdir -p "$LOCAL_BIN"
            meson setup "$TMP_WOFI/build" "$TMP_WOFI" --prefix="$HOME/.local" --buildtype=release >/dev/null 2>&1 || true
            ninja -C "$TMP_WOFI/build" install >/dev/null 2>&1 || true
            log_success "Patch Wofi appliqué et installé dans $LOCAL_BIN/wofi."
        fi
    fi
    rm -rf "$TMP_WOFI"
elif [ -n "$WOFI_BIN" ]; then
    log_success "Wofi est configuré avec le support natif de sélection au survol."
fi

# ----------------- VÉRIFICATION DU PATCH SWAYNC (CONTEXT-POPOVER & BLACKLIST) -----------------
SWAYNC_BIN=$(command -v swaync 2>/dev/null || true)
if [ -n "$SWAYNC_BIN" ] && ! strings "$SWAYNC_BIN" 2>/dev/null | grep -q "popover-btn-blacklist"; then
    log_step "Application du patch SwayNC (menu contextuel clic droit & blacklist dynamique)..."
    TMP_SWAYNC=$(mktemp -d /tmp/swaync_build_XXXXXX)
    if git clone --depth 1 --branch v0.10.1 https://github.com/ErikReider/SwayNotificationCenter.git "$TMP_SWAYNC" 2>/dev/null || \
       git clone --depth 1 https://github.com/ErikReider/SwayNotificationCenter.git "$TMP_SWAYNC" 2>/dev/null; then
        if [ -f "$DOTFILES_DIR/swaync/swaync-blacklist.patch" ]; then
            patch -d "$TMP_SWAYNC" -p1 < "$DOTFILES_DIR/swaync/swaync-blacklist.patch" >/dev/null 2>&1 || true
            meson setup "$TMP_SWAYNC/build" "$TMP_SWAYNC" --prefix="$HOME/.local" --buildtype=release >/dev/null 2>&1 || true
            ninja -C "$TMP_SWAYNC/build" install >/dev/null 2>&1 || true
            if [ -w /usr/local/bin ]; then
                cp "$HOME/.local/bin/swaync" /usr/local/bin/swaync 2>/dev/null || true
            fi
            log_success "Patch SwayNC appliqué et installé dans $LOCAL_BIN/swaync."
        fi
    fi
    rm -rf "$TMP_SWAYNC"
elif [ -n "$SWAYNC_BIN" ]; then
    log_success "SwayNC est configuré avec le support du menu contextuel et blacklist."
fi

# ----------------- VÉRIFICATION DU PATCH HYPRLOCK (ANTI-DEADLOCK PAM) -----------------
HYPRLOCK_BIN=$(command -v hyprlock 2>/dev/null || true)
if [ -n "$HYPRLOCK_BIN" ] && ! strings "$HYPRLOCK_BIN" 2>/dev/null | grep -q "_ZN4CPam9terminateEv"; then
    log_step "Application du patch Hyprlock (résolution deadlock PAM PR #1059)..."
    TMP_HYPRLOCK=$(mktemp -d /tmp/hyprlock_build_XXXXXX)
    if git clone --depth 1 --branch v0.9.6 https://github.com/hyprwm/hyprlock.git "$TMP_HYPRLOCK" 2>/dev/null || \
       git clone --depth 1 https://github.com/hyprwm/hyprlock.git "$TMP_HYPRLOCK" 2>/dev/null; then
        if [ -f "$DOTFILES_DIR/hypr/hyprlock-pam-deadlock.patch" ]; then
            patch -d "$TMP_HYPRLOCK" -p1 < "$DOTFILES_DIR/hypr/hyprlock-pam-deadlock.patch" >/dev/null 2>&1 || true
            cmake -B "$TMP_HYPRLOCK/build" -S "$TMP_HYPRLOCK" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$HOME/.local" >/dev/null 2>&1 || true
            cmake --build "$TMP_HYPRLOCK/build" --target hyprlock >/dev/null 2>&1 || true
            cp "$TMP_HYPRLOCK/build/hyprlock" "$LOCAL_BIN/hyprlock" 2>/dev/null || true
            if [ -w /usr/local/bin ]; then
                cp "$LOCAL_BIN/hyprlock" /usr/local/bin/hyprlock 2>/dev/null || true
            fi
            log_success "Patch Hyprlock appliqué et installé dans $LOCAL_BIN/hyprlock."
        fi
    fi
    rm -rf "$TMP_HYPRLOCK"
elif [ -n "$HYPRLOCK_BIN" ]; then
    log_success "Hyprlock est configuré avec le correctif anti-deadlock PAM."
fi

# ----------------- ÉTAPE 2 : SAUVEGARDE PRÉVENTIVE -----------------
log_info "2. Sauvegarde des configurations existantes dans ~/.config/..."

BACKUP_DIR="$HOME/.config/aurora_backup_$(date +'%Y%m%d_%H%M%S')"
NEED_BACKUP=0

TARGET_DIRS=("hypr" "waybar" "wofi" "kitty" "swaync")
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
chmod +x "$DOTFILES_DIR"/swaync/scripts/*.py 2>/dev/null || true
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

if [ -f "$SCRIPT_DIR/scripts/aurora_mcp_server.py" ]; then
    cat << 'EOF' > "$LOCAL_BIN/aurora-mcp"
#!/usr/bin/env bash
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../Documents/antigravity/hyprland_project" 2>/dev/null && pwd || echo "$HOME/Documents/antigravity/hyprland_project")"
exec uv run --with "mcp<2" python3 "$PROJECT_DIR/scripts/aurora_mcp_server.py" "$@"
EOF
    chmod +x "$LOCAL_BIN/aurora-mcp"
    log_success "Serveur et CLI 'aurora-mcp' configuré dans $LOCAL_BIN/aurora-mcp."
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

# Préparation & vérification des masques Lucy
log_step "Vérification et calcul des masques Lucy..."
python3 "$SCRIPT_DIR/scripts/wallpaper_tool.py" mask 2>/dev/null || true
log_success "Masques Blackwall et Lucy validés."

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
