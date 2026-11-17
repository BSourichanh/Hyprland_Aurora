#!/usr/bin/env bash
# ==============================================================================
# Aurora Setup Module: Packages & System Dependencies
# Installs core Wayland packages, C99 build headers, uv, and Nautilus integration.
# Usage: packages.sh [--nautilus-only]
# ==============================================================================

set -eo pipefail

COLOR_CYAN="\033[38;2;0;240;255m"
COLOR_BLUE="\033[38;2;122;162;247m"
COLOR_GREEN="\033[38;2;115;218;202m"
COLOR_PURPLE="\033[38;2;151;120;208m"
COLOR_RED="\033[38;2;247;118;142m"
COLOR_RESET="\033[0m"
BOLD="\033[1m"

log_info()    { echo -e "${COLOR_BLUE}==>${COLOR_RESET} ${BOLD}$*${COLOR_RESET}"; }
log_step()    { echo -e "${COLOR_CYAN}  ->${COLOR_RESET} $*"; }
log_success() { echo -e "${COLOR_GREEN}  ✓${COLOR_RESET} ${BOLD}$*${COLOR_RESET}"; }
log_warn()    { echo -e "${COLOR_PURPLE}  !${COLOR_RESET} ${BOLD}$*${COLOR_RESET}"; }
log_error()   { echo -e "${COLOR_RED}  ✗ ERREUR :${COLOR_RESET} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SYSTEM_PKGS=(
    waybar wofi kitty hyprland hyprlock hypridle hyprpicker swaybg slurp grim
    wl-clipboard playerctl pavucontrol jq wireplumber x11-xserver-utils
    libnotify-bin brightnessctl python3 python3-gi python3-dbus python3-pil
    python3-nautilus gir1.2-nautilus-4.0 gettext fonts-noto fonts-font-awesome
    fonts-jetbrains-mono meson ninja-build cmake build-essential pkg-config
    libgtk-3-dev libwayland-dev libegl-dev libgles-dev wtype
    sway-notification-center curl git binutils patch
)

ensure_uv() {
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv >/dev/null 2>&1; then
        log_success "Outil 'uv' disponible ($(command -v uv))."
        return 0
    fi
    log_step "Installation de 'uv' (requis pour le serveur aurora-mcp)..."
    if ! command -v curl >/dev/null 2>&1; then
        log_error "'curl' est requis pour installer 'uv'."
        return 1
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
        log_error "L'installation de 'uv' a échoué."
        return 1
    fi
    log_success "Outil 'uv' installé dans $HOME/.local/bin/uv."
}

install_packages() {
    log_info "1. Vérification et installation des dépendances système..."

    if command -v apt-get >/dev/null 2>&1; then
        log_step "Gestionnaire apt détecté (Ubuntu / Debian)."
        if ! command -v hyprland >/dev/null 2>&1 && ! apt-cache show hyprland >/dev/null 2>&1; then
            if ! command -v add-apt-repository >/dev/null 2>&1; then
                sudo apt-get update
                sudo apt-get install -y software-properties-common
            fi
            log_step "Ajout du dépôt PPA cppiber/hyprland pour Ubuntu..."
            sudo add-apt-repository -y ppa:cppiber/hyprland
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

        if dpkg -s nautilus-extension-gnome-terminal >/dev/null 2>&1; then
            log_step "Désinstallation de nautilus-extension-gnome-terminal (conflit)..."
            sudo apt-get remove -y nautilus-extension-gnome-terminal || true
            log_success "Conflit GNOME Terminal retiré."
        fi
    elif command -v pacman >/dev/null 2>&1; then
        log_step "Gestionnaire pacman détecté (Arch Linux). Installation..."
        sudo pacman -S --needed --noconfirm \
            hyprland waybar wofi kitty hyprlock hypridle hyprpicker swaync swaybg \
            slurp grim wl-clipboard playerctl pavucontrol jq wireplumber xorg-xrandr \
            libnotify brightnessctl python python-gobject python-dbus python-pillow \
            python-nautilus gettext noto-fonts ttf-font-awesome ttf-jetbrains-mono \
            meson ninja cmake base-devel pkgconf libglvnd wayland egl-wayland mesa \
            curl git binutils patch uv
    else
        log_warn "Gestionnaire de paquets inconnu. Vérifiez la présence des dépendances Wayland/EGL/GLES2."
    fi

    ensure_uv
}

configure_nautilus() {
    log_step "Configuration de l'extension Nautilus (clic droit -> Kitty, espace utilisateur)..."
    local ext_src="$SCRIPT_DIR/ressource/nautilus/nautilus_open_any_terminal.py"
    local schema_src="$SCRIPT_DIR/ressource/nautilus/com.github.stunkymonkey.nautilus-open-any-terminal.gschema.xml"
    local sys_ext="/usr/share/nautilus-python/extensions/nautilus_open_any_terminal.py"
    local sys_schema="/usr/share/glib-2.0/schemas/com.github.stunkymonkey.nautilus-open-any-terminal.gschema.xml"
    local user_ext_dir="$HOME/.local/share/nautilus-python/extensions"
    local user_schema_dir="$HOME/.local/share/glib-2.0/schemas"

    if [ -f "$ext_src" ] && [ -f "$sys_ext" ] && cmp -s "$ext_src" "$sys_ext" && [ -f "$sys_schema" ]; then
        rm -f "$user_ext_dir/nautilus_open_any_terminal.py"
        gsettings set com.github.stunkymonkey.nautilus-open-any-terminal terminal 'kitty' 2>/dev/null || true
        log_success "Extension système Nautilus identique détectée ; terminal défini sur Kitty."
        return 0
    fi

    mkdir -p "$user_ext_dir" "$user_schema_dir"
    if [ -f "$ext_src" ]; then
        install -m 644 "$ext_src" "$user_ext_dir/nautilus_open_any_terminal.py"
    fi
    if [ -f "$schema_src" ]; then
        install -m 644 "$schema_src" "$user_schema_dir/com.github.stunkymonkey.nautilus-open-any-terminal.gschema.xml"
        if command -v glib-compile-schemas >/dev/null 2>&1; then
            glib-compile-schemas "$user_schema_dir"
        fi
        gsettings --schemadir "$user_schema_dir" set com.github.stunkymonkey.nautilus-open-any-terminal terminal 'kitty' 2>/dev/null || true
    fi
    nautilus -q 2>/dev/null || true
    log_success "Nautilus configuré dans ~/.local/share/ (sans sudo bloquant) pour ouvrir Kitty."
}

main() {
    if [ "${1:-}" = "--nautilus-only" ]; then
        configure_nautilus
    else
        install_packages
        configure_nautilus
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
