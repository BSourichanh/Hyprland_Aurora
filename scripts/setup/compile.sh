#!/usr/bin/env bash
# ==============================================================================
# Aurora Setup Module: Compilation & Patches
# Compiles native C99 wallpaper engine and applies ergonomic desktop patches.
# All binaries are deployed strictly to $HOME/.local/bin (no root override).
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
DOTFILES_DIR="$SCRIPT_DIR/dotfiles"
LOCAL_BIN="$HOME/.local/bin"
LOCAL_SHARE="$HOME/.local/share/aurora-wallpaper"

mkdir -p "$LOCAL_BIN"

resolve_binary_priority() {
    local name="$1"
    if [ -x "$LOCAL_BIN/$name" ]; then
        echo "$LOCAL_BIN/$name"
    else
        command -v "$name" 2>/dev/null || true
    fi
}

compile_aurora_wallpaper() {
    log_info "2. Compilation et installation du moteur de fond d'écran Aurora..."
    local src_dir="$SCRIPT_DIR/src/aurora_wallpaper"
    if [ ! -d "$src_dir" ]; then
        log_error "Dossier source $src_dir introuvable."
        return 1
    fi

    if ! make -C "$src_dir"; then
        log_error "Échec de compilation de aurora-wallpaper dans $src_dir."
        return 1
    fi

    if [ ! -x "$LOCAL_BIN/aurora-wallpaper" ] || ! cmp -s "$src_dir/aurora-wallpaper" "$LOCAL_BIN/aurora-wallpaper"; then
        if ! make -C "$src_dir" install; then
            log_error "Échec de l'installation de aurora-wallpaper vers $LOCAL_BIN."
            return 1
        fi
        log_success "aurora-wallpaper compilé et installé dans $LOCAL_BIN/aurora-wallpaper."
    else
        log_success "aurora-wallpaper est compilé et à jour dans $LOCAL_BIN."
    fi

    mkdir -p "$LOCAL_SHARE/ressource/blackwall"
    if [ -f "$SCRIPT_DIR/ressource/lucy.png" ]; then
        install -m 644 "$SCRIPT_DIR/ressource/lucy.png" "$LOCAL_SHARE/ressource/lucy.png"
    fi
    if [ -f "$SCRIPT_DIR/ressource/blackwall/blackwall_mask.png" ]; then
        install -m 644 "$SCRIPT_DIR/ressource/blackwall/blackwall_mask.png" "$LOCAL_SHARE/ressource/blackwall/blackwall_mask.png"
    fi
    log_success "Ressources runtime synchronisées dans $LOCAL_SHARE."
}

check_hyprspace() {
    for plugin in "Hyprspace.so" "hyprglass.so"; do
        local plugin_path="$DOTFILES_DIR/hypr/plugins/$plugin"
        if [ -f "$plugin_path" ]; then
            if [ "$(stat -c %a "$plugin_path" 2>/dev/null || true)" != "775" ]; then
                chmod 775 "$plugin_path"
            fi
            if [ -r "$plugin_path" ] && [ -x "$plugin_path" ]; then
                log_success "Plugin $plugin validé et exécutable ($plugin_path)."
            else
                log_error "Permissions invalides sur le plugin $plugin_path."
                return 1
            fi
        else
            log_warn "Plugin $plugin absent dans $DOTFILES_DIR/hypr/plugins (recompilation requise contre les en-têtes Hyprland)."
        fi
    done
}

link_local_cli() {
    local src_path="$1"
    local bin_name="$2"
    local dst_path="$LOCAL_BIN/$bin_name"

    if [ ! -f "$src_path" ]; then
        log_warn "Utilitaire source absent : $src_path"
        return 0
    fi
    [ -x "$src_path" ] || chmod 755 "$src_path"

    if [ "$(stat -c %d "$(dirname "$src_path")")" = "$(stat -c %d "$LOCAL_BIN")" ]; then
        if [ -f "$dst_path" ] && [ ! -L "$dst_path" ] && [ "$(stat -c %i "$src_path")" = "$(stat -c %i "$dst_path")" ]; then
            log_success "Utilitaire '$bin_name' déjà lié par hardlink dans $dst_path."
        else
            rm -f "$dst_path"
            ln "$src_path" "$dst_path"
            log_success "Utilitaire '$bin_name' déployé par hardlink dans $dst_path."
        fi
    else
        ln -sf "$src_path" "$dst_path"
        log_success "Utilitaire '$bin_name' déployé par symlink dans $dst_path."
    fi
}

sync_cli_tools() {
    log_step "Vérification et liaison des utilitaires CLI dans $LOCAL_BIN..."
    link_local_cli "$SCRIPT_DIR/scripts/aurora_osd.py" "aurora-osd"
    link_local_cli "$SCRIPT_DIR/scripts/hyprbar" "hyprbar"
}

patch_wofi() {
    local wofi_bin
    wofi_bin="$(resolve_binary_priority wofi)"
    if [ -z "$wofi_bin" ]; then
        log_warn "wofi absent : patch ignoré."
        return 0
    fi
    if strings "$wofi_bin" 2>/dev/null | grep -q "on_motion_select"; then
        log_success "Wofi ($wofi_bin) est configuré avec la sélection au survol."
        return 0
    fi
    if [ ! -f "$DOTFILES_DIR/wofi/wofi-hover-select.patch" ]; then
        log_error "Patch introuvable : $DOTFILES_DIR/wofi/wofi-hover-select.patch"
        return 1
    fi

    log_step "Application du patch Wofi (sélection active au survol)..."
    local tmp_wofi
    tmp_wofi="$(mktemp -d /tmp/wofi_build_XXXXXX)"
    trap 'rm -rf "$tmp_wofi"' RETURN

    curl -fsSL https://hg.sr.ht/~scoopta/wofi/archive/v1.4.1.tar.gz | tar -xzf - -C "$tmp_wofi" --strip-components=1
    patch -d "$tmp_wofi" -p1 < "$DOTFILES_DIR/wofi/wofi-hover-select.patch"
    meson setup "$tmp_wofi/build" "$tmp_wofi" --prefix="$HOME/.local" --buildtype=release
    ninja -C "$tmp_wofi/build" install
    log_success "Patch Wofi appliqué dans $LOCAL_BIN/wofi."
}

patch_swaync() {
    local swaync_bin
    swaync_bin="$(resolve_binary_priority swaync)"
    if [ -z "$swaync_bin" ]; then
        log_warn "swaync absent : patch ignoré."
        return 0
    fi
    if strings "$swaync_bin" 2>/dev/null | grep -q "popover-btn-blacklist"; then
        log_success "SwayNC ($swaync_bin) est configuré avec le menu contextuel et blacklist."
        return 0
    fi
    if [ ! -f "$DOTFILES_DIR/swaync/swaync-blacklist.patch" ]; then
        log_error "Patch introuvable : $DOTFILES_DIR/swaync/swaync-blacklist.patch"
        return 1
    fi

    log_step "Application du patch SwayNC (menu contextuel & blacklist)..."
    local tmp_swaync
    tmp_swaync="$(mktemp -d /tmp/swaync_build_XXXXXX)"
    trap 'rm -rf "$tmp_swaync"' RETURN

    git clone --depth 1 --branch v0.10.1 https://github.com/ErikReider/SwayNotificationCenter.git "$tmp_swaync"
    patch -d "$tmp_swaync" -p1 < "$DOTFILES_DIR/swaync/swaync-blacklist.patch"
    meson setup "$tmp_swaync/build" "$tmp_swaync" --prefix="$HOME/.local" --buildtype=release
    ninja -C "$tmp_swaync/build" install
    log_success "Patch SwayNC appliqué dans $LOCAL_BIN/swaync."
}

is_hyprlock_patched() {
    local bin="$1"
    [ -x "$bin" ] || return 1
    if ! command -v objdump >/dev/null 2>&1; then
        log_warn "objdump introuvable : impossible de vérifier le désassemblage PAM sur $bin."
        return 1
    fi
    local pam_dtor fade_fn
    pam_dtor="$(objdump -d -C "$bin" 2>/dev/null | awk '/<CPam::~CPam\(\)>:/,/^$/')"
    fade_fn="$(objdump -d -C "$bin" 2>/dev/null | awk '/<CHyprlock::isFadingOutOrTerminating\(\)>:/,/^$/')"
    if [ -z "$pam_dtor" ] || [ -z "$fade_fn" ]; then
        log_warn "Binaire $bin strippé ou symboles PAM absents : vérification patch impossible."
        return 1
    fi
    echo "$pam_dtor" | grep -q "notify_all" && echo "$fade_fn" | grep -q "0xfa("
}

patch_hyprlock() {
    local hyprlock_bin
    hyprlock_bin="$(resolve_binary_priority hyprlock)"
    if [ -z "$hyprlock_bin" ]; then
        log_warn "hyprlock absent : patch ignoré."
        return 0
    fi
    if is_hyprlock_patched "$hyprlock_bin"; then
        log_success "Hyprlock ($hyprlock_bin) contient le correctif anti-deadlock PAM vérifié par objdump."
        return 0
    fi
    if [ ! -f "$DOTFILES_DIR/hypr/hyprlock-pam-deadlock.patch" ]; then
        log_error "Patch introuvable : $DOTFILES_DIR/hypr/hyprlock-pam-deadlock.patch"
        return 1
    fi

    log_step "Compilation et application du patch Hyprlock (anti-deadlock PAM)..."
    local tmp_hyprlock
    tmp_hyprlock="$(mktemp -d /tmp/hyprlock_build_XXXXXX)"
    trap 'rm -rf "$tmp_hyprlock"' RETURN

    git clone --depth 1 --branch v0.9.6 https://github.com/hyprwm/hyprlock.git "$tmp_hyprlock"
    patch -d "$tmp_hyprlock" -p1 < "$DOTFILES_DIR/hypr/hyprlock-pam-deadlock.patch"
    cmake -B "$tmp_hyprlock/build" -S "$tmp_hyprlock" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$HOME/.local"
    cmake --build "$tmp_hyprlock/build" --target hyprlock -j"$(nproc 2>/dev/null || echo 2)"
    if ! is_hyprlock_patched "$tmp_hyprlock/build/hyprlock"; then
        log_error "Le binaire hyprlock compilé ne contient pas les marqueurs du patch PAM !"
        return 1
    fi
    install -m 755 "$tmp_hyprlock/build/hyprlock" "$LOCAL_BIN/hyprlock"
    log_success "Patch Hyprlock compilé, vérifié et installé dans $LOCAL_BIN/hyprlock."
}

main() {
    compile_aurora_wallpaper
    check_hyprspace
    sync_cli_tools
    patch_wofi
    patch_swaync
    patch_hyprlock
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
