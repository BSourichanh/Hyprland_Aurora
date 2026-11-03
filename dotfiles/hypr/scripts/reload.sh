#!/bin/bash
# Rechargement de la configuration Hyprland et redémarrage de Waybar

# Protection session verrouillée : neutraliser tout rechargement
if [ -f "/tmp/hypr_locked" ] || hyprctl layers 2>/dev/null | grep -q "namespace: hyprlock"; then
    exit 0
fi

hyprctl reload

if [ -x "$HOME/.local/bin/hyprbar" ]; then
    "$HOME/.local/bin/hyprbar" restart >/dev/null 2>&1
else
    killall waybar 2>/dev/null
    pkill -9 -f "spotify-card.py" 2>/dev/null
    pkill -f "spotify.py" 2>/dev/null
    pkill -f "gpu.py" 2>/dev/null
    pkill -f "swaync-client -swb" 2>/dev/null
    sleep 0.3
    hyprctl dispatch exec waybar >/dev/null 2>&1
    hyprctl dispatch exec "$HOME/.config/waybar/scripts/spotify-card.py daemon" >/dev/null 2>&1
fi

notify-send -u low -i "view-refresh" "Hyprland" "Configuration et Waybar rechargées" 2>/dev/null || true
