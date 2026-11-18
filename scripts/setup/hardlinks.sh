#!/usr/bin/env bash
# ==============================================================================
# Aurora Setup Module: Hard Links & Inode Integrity
# Deploys individual physical hard links (ln) for every canonical dotfile to ~/.config/.
# Eliminates directory-level symlinks, guards EXDEV, and cleans stale files.
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
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
MANAGED_DIRS=("hypr" "waybar" "wofi" "kitty" "swaync")

check_same_filesystem() {
    mkdir -p "$CONFIG_DIR"
    local src_dev dst_dev
    src_dev="$(stat -c %d "$DOTFILES_DIR")"
    dst_dev="$(stat -c %d "$CONFIG_DIR")"
    if [ "$src_dev" != "$dst_dev" ]; then
        log_error "Impossible de créer des hardlinks cross-filesystem (EXDEV : $DOTFILES_DIR [dev=$src_dev] != $CONFIG_DIR [dev=$dst_dev])."
        exit 1
    fi
}

needs_backup() {
    local d
    for d in "${MANAGED_DIRS[@]}"; do
        if [ -L "$CONFIG_DIR/$d" ]; then
            return 0
        fi
    done

    while IFS= read -r -d '' src_file; do
        local rel_path="${src_file#$DOTFILES_DIR/}"
        local dst_file="$CONFIG_DIR/$rel_path"
        if [ -L "$dst_file" ]; then
            return 0
        fi
        if [ -e "$dst_file" ] && [ "$(stat -c %i "$src_file")" != "$(stat -c %i "$dst_file")" ]; then
            return 0
        fi
    done < <(find "$DOTFILES_DIR" -type f -not -name "*.bak" -not -name "*-bak" -not -name "*.pyc" -not -path "*/__pycache__/*" -print0)

    return 1
}

backup_configs() {
    local force_backup="${1:-0}"
    if [ "$force_backup" -eq 0 ] && ! needs_backup; then
        log_step "Tous les liens existants sont déjà alignés : sauvegarde préventive ignorée."
        return 0
    fi

    local backup_dir="$CONFIG_DIR/aurora_backup_$(date +'%Y%m%d_%H%M%S')"
    log_info "Sauvegarde des configurations conflictuelles dans $backup_dir..."
    mkdir -p "$backup_dir"
    local d
    for d in "${MANAGED_DIRS[@]}"; do
        if [ -e "$CONFIG_DIR/$d" ]; then
            log_step "Archivage de ~/.config/$d..."
            cp -r --preserve=all "$CONFIG_DIR/$d" "$backup_dir/" 2>/dev/null || true
        fi
    done
    log_success "Sauvegarde créée dans : $backup_dir"
}

replace_dir_symlinks() {
    log_info "3. Remplacement des liens symboliques de répertoires par des répertoires physiques..."
    local d
    for d in "${MANAGED_DIRS[@]}"; do
        local target_path="$CONFIG_DIR/$d"
        if [ -L "$target_path" ]; then
            log_step "Suppression du symlink répertoire : $target_path"
            rm -f "$target_path"
            mkdir -p "$target_path"
        elif [ ! -d "$target_path" ]; then
            mkdir -p "$target_path"
        fi
    done
}

cleanup_stale_targets() {
    local cleaned=0
    local d
    for d in "${MANAGED_DIRS[@]}"; do
        local dir_path="$CONFIG_DIR/$d"
        [ -d "$dir_path" ] || continue
        while IFS= read -r -d '' dst_item; do
            local rel_path="${dst_item#$CONFIG_DIR/}"
            local expected_src="$DOTFILES_DIR/$rel_path"
            if [ -L "$dst_item" ] || [ ! -e "$expected_src" ] || [[ "$dst_item" == *.bak ]] || [[ "$dst_item" == *-bak ]]; then
                rm -f "$dst_item"
                cleaned=$((cleaned + 1))
            fi
        done < <(find "$dir_path" \( -type f -o -type l \) -not -path "*/__pycache__/*" -not -name "*.pyc" -print0)
    done
    if [ "$cleaned" -gt 0 ]; then
        log_step "$cleaned fichier(s) ou lien(s) obsolète(s) nettoyé(s) dans ~/.config/."
    fi
}

deploy_hardlinks() {
    log_info "4. Établissement des vrais hard links individuels (st_nlink >= 2)..."
    mkdir -p "$CONFIG_DIR"
    local total_links=0

    while IFS= read -r -d '' src_file; do
        local rel_path="${src_file#$DOTFILES_DIR/}"
        local dst_file="$CONFIG_DIR/$rel_path"

        mkdir -p "$(dirname "$dst_file")"

        if [ -L "$dst_file" ]; then
            rm -f "$dst_file"
        fi

        if [ -e "$dst_file" ]; then
            local src_ino dst_ino
            src_ino="$(stat -c %i "$src_file")"
            dst_ino="$(stat -c %i "$dst_file")"
            if [ "$src_ino" = "$dst_ino" ] && [ "$(stat -c %h "$dst_file")" -ge 2 ]; then
                total_links=$((total_links + 1))
                continue
            fi
            rm -f "$dst_file"
        fi

        ln "$src_file" "$dst_file"
        total_links=$((total_links + 1))
    done < <(find "$DOTFILES_DIR" -type f -not -name "*.bak" -not -name "*-bak" -not -name "*.pyc" -not -path "*/__pycache__/*" -print0)

    log_success "$total_links vrais hard links établis entre dotfiles/ et ~/.config/."
}

main() {
    local force_backup="${1:-0}"
    check_same_filesystem
    backup_configs "$force_backup"
    replace_dir_symlinks
    cleanup_stale_targets
    deploy_hardlinks
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
