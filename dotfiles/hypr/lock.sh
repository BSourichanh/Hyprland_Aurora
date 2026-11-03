#!/bin/bash
# Protocole de Verrouillage Sécurisé Hyprland / Aurora Theme
# Support multi-écrans dynamique & protection anti-fuite de workspaces

LOCK_FLAG="/tmp/hypr_locked"
STATE_FILE="/tmp/hypr_lock_orig_workspaces.json"
INSTANCE_LOCK="/tmp/hypr_lock_instance.lock"
HELPER_SCRIPT="$HOME/.config/hypr/scripts/hyprlock_state.py"
[ -f "$HELPER_SCRIPT" ] || HELPER_SCRIPT="$HOME/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/hyprlock_state.py"

# Mutex singleton atomique : interdire toute exécution concurrente
exec 9>"$INSTANCE_LOCK"
if ! flock -n 9; then exit 0; fi

# Purge préventive de tout hyprlock orphelin
if pidof hyprlock >/dev/null; then
    killall -9 hyprlock 2>/dev/null
    sleep 0.05
fi

CLEANED=0
WATCHER_PID=""
WAYBAR_WAS_RUNNING=0
PREV_DND="false"

# Gestionnaire de nettoyage déterministe (RAII)
cleanup() {
    [ "$CLEANED" -eq 1 ] && return
    CLEANED=1

    [ -n "$WATCHER_PID" ] && { kill "$WATCHER_PID" 2>/dev/null; wait "$WATCHER_PID" 2>/dev/null; }
    rm -f "$LOCK_FLAG"
    hyprctl keyword misc:disable_autoreload false >/dev/null 2>&1

    python3 "$HELPER_SCRIPT" restore >/dev/null 2>&1
    rm -f "$STATE_FILE"

    if [ "$WAYBAR_WAS_RUNNING" -eq 1 ]; then
        pkill -f "spotify.py --progress" 2>/dev/null
        hyprctl dispatch exec waybar >/dev/null 2>&1
    fi

    python3 "$HOME/.config/hypr/scripts/workspace-autocompact.py" --once >/dev/null 2>&1 9>&- &
    python3 "$HOME/Documents/antigravity/hyprland_project/scripts/wallpaper_tool.py" ensure >/dev/null 2>&1 9>&- &
    (sleep 0.5 && python3 "$HOME/Documents/antigravity/hyprland_project/scripts/wallpaper_tool.py" ensure >/dev/null 2>&1) 9>&- &

    if [ "$PREV_DND" = "false" ]; then
        timeout 0.5 swaync-client -df -sw >/dev/null 2>&1 9>&- &
    fi

    flock -u 9 2>/dev/null
    exec 9>&-
}

trap cleanup EXIT INT TERM

touch "$LOCK_FLAG"
hyprctl keyword misc:disable_autoreload true >/dev/null 2>&1

# Capture de l'état, basculement vers workspaces réservés et démarrage watcher
python3 "$HELPER_SCRIPT" save >/dev/null 2>&1
python3 "$HELPER_SCRIPT" switch-reserved >/dev/null 2>&1
python3 "$HELPER_SCRIPT" watch 9>&- &
WATCHER_PID=$!

# Fermer popups et cartes Waybar
pkill -x wofi 2>/dev/null
"$HOME/.config/waybar/scripts/spotify-card.py" hide >/dev/null 2>&1 9>&- &

# Suspendre notifications et arrêter Waybar pendant le verrouillage
PREV_DND=$(timeout 0.5 swaync-client -D -sw 2>/dev/null || echo "false")
timeout 0.5 swaync-client -cp -sw >/dev/null 2>&1 9>&- &
timeout 0.5 swaync-client -dn -sw >/dev/null 2>&1 9>&- &

if pgrep -x waybar >/dev/null; then
    WAYBAR_WAS_RUNNING=1
    killall waybar 2>/dev/null
    pkill -f "spotify.py" 2>/dev/null
    pkill -f "gpu.py" 2>/dev/null
    pkill -f "swaync-client -swb" 2>/dev/null
    sleep 0.05
fi

# Expulsion résiduelle des fenêtres et affichage du verrou (Lucy reste active en arrière-plan)
python3 "$HELPER_SCRIPT" expel-clients >/dev/null 2>&1
hyprlock 9>&-

cleanup

