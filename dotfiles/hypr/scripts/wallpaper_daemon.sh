#!/usr/bin/env bash
# Daemon launcher for Wallpaper Engine (Lucy) with portable path resolution
PROJECT_DIR=""
for candidate in \
    "$HOME/Documents/antigravity/hyprland_project" \
    "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd)" \
    "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../Documents/antigravity/hyprland_project" 2>/dev/null && pwd)"; do
    if [ -f "$candidate/scripts/wallpaper_tool.py" ]; then
        PROJECT_DIR="$candidate"
        break
    fi
done

if [ -z "$PROJECT_DIR" ]; then
    echo "Erreur: Impossible de localiser scripts/wallpaper_tool.py" >&2
    exit 1
fi

exec python3 "$PROJECT_DIR/scripts/wallpaper_tool.py" daemon
