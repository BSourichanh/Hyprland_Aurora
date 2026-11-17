#!/usr/bin/env bash
# Daemon launcher for Wallpaper Engine (Lucy) with portable path resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
HYPRBAR_TARGET=""
if [ -e "$HOME/.local/bin/hyprbar" ]; then
    HYPRBAR_TARGET="$(readlink -f "$HOME/.local/bin/hyprbar" 2>/dev/null || true)"
fi
HYPRBAR_ROOT="${HYPRBAR_TARGET%/scripts/hyprbar}"
[ "$HYPRBAR_ROOT" = "$HYPRBAR_TARGET" ] && HYPRBAR_ROOT=""

PROJECT_DIR=""
for candidate in \
    "${AURORA_PROJECT_DIR:-}" \
    "$(cd "$SCRIPT_DIR/../../.." 2>/dev/null && pwd)" \
    "$HYPRBAR_ROOT" \
    "$HOME/Documents/antigravity/hyprland_project" \
    "$HOME/hyprland_project"; do
    if [ -n "$candidate" ] && [ -f "$candidate/scripts/wallpaper_tool.py" ]; then
        PROJECT_DIR="$candidate"
        break
    fi
done

if [ -z "$PROJECT_DIR" ]; then
    echo "Erreur: Impossible de localiser scripts/wallpaper_tool.py" >&2
    exit 1
fi

exec python3 -B "$PROJECT_DIR/scripts/wallpaper_tool.py" daemon
