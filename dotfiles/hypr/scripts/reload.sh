#!/bin/bash
# Rechargement de la configuration Hyprland et redémarrage propre de Waybar & SwayNC

AURORA_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora"

# Protection session verrouillée : neutraliser tout rechargement (pgrep + flock)
if pgrep -x hyprlock >/dev/null 2>&1; then
    exit 0
fi
if [ -f "$AURORA_RUNTIME_DIR/hypr_locked" ] && command -v flock >/dev/null 2>&1; then
    if ! flock -n "$AURORA_RUNTIME_DIR/hypr_lock_instance.lock" true 2>/dev/null; then
        exit 0
    fi
fi

hyprctl reload

if [ -x "$HOME/.local/bin/hyprbar" ]; then
    "$HOME/.local/bin/hyprbar" restart >/dev/null 2>&1
else
    pkill -TERM -x waybar 2>/dev/null || true
    pkill -TERM -f "waybar/scripts/spotify-card.py" 2>/dev/null || true
    pkill -TERM -f "waybar/scripts/spotify.py" 2>/dev/null || true
    pkill -TERM -f "waybar/scripts/gpu.py" 2>/dev/null || true
    pkill -TERM -f "swaync-client -swb" 2>/dev/null || true

    for _ in $(seq 1 15); do
        if ! pgrep -x waybar >/dev/null 2>&1 && ! pgrep -f "waybar/scripts/spotify-card.py" >/dev/null 2>&1; then
            break
        fi
        sleep 0.05
    done
    if pgrep -f "waybar/scripts/spotify-card.py" >/dev/null 2>&1; then
        pkill -KILL -f "waybar/scripts/spotify-card.py" 2>/dev/null || true
    fi
    rm -f "$AURORA_RUNTIME_DIR/spotify_card.sock" 2>/dev/null || true

    hyprctl dispatch exec waybar >/dev/null 2>&1
    hyprctl dispatch exec "$HOME/.config/waybar/scripts/spotify-card.py daemon" >/dev/null 2>&1
fi

swaync-client -R >/dev/null 2>&1 || true
swaync-client -rs >/dev/null 2>&1 || true

notify-send -u low -i "view-refresh" "Hyprland" "Configuration et Waybar rechargées" 2>/dev/null || true
