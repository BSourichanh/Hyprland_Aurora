#!/bin/bash
# Protocole de Verrouillage Sécurisé Hyprland / Aurora Theme
# Support multi-écrans dynamique & protection anti-fuite de workspaces

AURORA_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora"
mkdir -p -m 700 "$AURORA_RUNTIME_DIR"
chmod 700 "$AURORA_RUNTIME_DIR" 2>/dev/null || true

LOCK_FLAG="$AURORA_RUNTIME_DIR/hypr_locked"
STATE_FILE="$AURORA_RUNTIME_DIR/hypr_lock_orig_workspaces.json"
INSTANCE_LOCK="$AURORA_RUNTIME_DIR/hypr_lock_instance.lock"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
HELPER_SCRIPT="$HOME/.config/hypr/scripts/hyprlock_state.py"
[ -f "$HELPER_SCRIPT" ] || HELPER_SCRIPT="$SCRIPT_DIR/scripts/hyprlock_state.py"

resolve_wallpaper_tool() {
    local candidate
    for candidate in \
        "${AURORA_PROJECT_DIR:-}/scripts/wallpaper_tool.py" \
        "$SCRIPT_DIR/../../scripts/wallpaper_tool.py" \
        "$HOME/Documents/antigravity/hyprland_project/scripts/wallpaper_tool.py" \
        "$HOME/hyprland_project/scripts/wallpaper_tool.py"; do
        if [ -n "$candidate" ] && [ -f "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

# Mutex singleton atomique : interdire toute exécution concurrente
touch "$INSTANCE_LOCK"
chmod 600 "$INSTANCE_LOCK" 2>/dev/null || true
exec 9>"$INSTANCE_LOCK"
if ! flock -n 9; then exit 0; fi

# Purge préventive de tout hyprlock orphelin
if pgrep -x hyprlock >/dev/null 2>&1; then
    pkill -TERM -x hyprlock 2>/dev/null || true
    sleep 0.1
    if pgrep -x hyprlock >/dev/null 2>&1; then
        pkill -KILL -x hyprlock 2>/dev/null || true
        sleep 0.05
    fi
fi

CLEANED=0
WATCHER_PID=""
WAYBAR_WAS_RUNNING=0
PREV_DND="false"

# Gestionnaire de nettoyage déterministe (RAII)
cleanup() {
    [ "$CLEANED" -eq 1 ] && return
    CLEANED=1

    # Sur SIGTERM/INT, terminer hyprlock s'il tourne encore avant de démasquer l'écran
    if pgrep -x hyprlock >/dev/null 2>&1; then
        pkill -TERM -x hyprlock 2>/dev/null || true
        for _ in $(seq 1 20); do
            pgrep -x hyprlock >/dev/null 2>&1 || break
            sleep 0.05
        done
        if pgrep -x hyprlock >/dev/null 2>&1; then
            pkill -KILL -x hyprlock 2>/dev/null || true
        fi
    fi

    [ -n "$WATCHER_PID" ] && { kill "$WATCHER_PID" 2>/dev/null; wait "$WATCHER_PID" 2>/dev/null; }
    rm -f "$LOCK_FLAG"
    hyprctl keyword misc:disable_autoreload false >/dev/null 2>&1

    python3 -B "$HELPER_SCRIPT" restore >/dev/null 2>&1
    rm -f "$STATE_FILE"

    if [ "$WAYBAR_WAS_RUNNING" -eq 1 ]; then
        pkill -f "waybar/scripts/spotify.py --progress" 2>/dev/null || true
        for _ in $(seq 1 20); do
            pgrep -x waybar >/dev/null 2>&1 || break
            sleep 0.05
        done
        hyprctl dispatch exec waybar >/dev/null 2>&1
    fi

    python3 -B "$HOME/.config/hypr/scripts/workspace-autocompact.py" --once >/dev/null 2>&1 9>&- &
    WALLPAPER_TOOL="$(resolve_wallpaper_tool || true)"
    if [ -n "$WALLPAPER_TOOL" ]; then
        python3 -B "$WALLPAPER_TOOL" ensure >/dev/null 2>&1 9>&- &
    fi

    if [ "$PREV_DND" = "false" ]; then
        timeout 0.5 swaync-client -df -sw >/dev/null 2>&1 9>&- &
    fi

    flock -u 9 2>/dev/null
    exec 9>&-
}

on_signal() {
    cleanup
    exit 143
}

trap cleanup EXIT
trap on_signal INT TERM

umask 077
touch "$LOCK_FLAG"
chmod 600 "$LOCK_FLAG" 2>/dev/null || true
hyprctl keyword misc:disable_autoreload true >/dev/null 2>&1

# 1. Fermer popups, cartes Waybar et overlays immédiatement
pkill -x wofi 2>/dev/null || true
"$HOME/.config/waybar/scripts/spotify-card.py" hide >/dev/null 2>&1 || true

# 2. Suspendre SwayNC DND de manière strictement synchrone AVANT hyprlock (supprime la fuite 50-100ms)
PREV_DND=$(timeout 0.5 swaync-client -D -sw 2>/dev/null || echo "false")
timeout 0.5 swaync-client -cp -sw >/dev/null 2>&1 || true
timeout 0.5 swaync-client -dn -sw >/dev/null 2>&1 || true

# 3. Arrêter Waybar de manière synchrone et attendre sa disparition propre
if pgrep -x waybar >/dev/null 2>&1; then
    WAYBAR_WAS_RUNNING=1
    pkill -TERM -x waybar 2>/dev/null || true
    pkill -TERM -f "waybar/scripts/spotify.py" 2>/dev/null || true
    pkill -TERM -f "waybar/scripts/gpu.py" 2>/dev/null || true
    pkill -TERM -f "swaync-client -swb" 2>/dev/null || true
    for _ in $(seq 1 20); do
        pgrep -x waybar >/dev/null 2>&1 || break
        sleep 0.05
    done
    if pgrep -x waybar >/dev/null 2>&1; then
        pkill -KILL -x waybar 2>/dev/null || true
        sleep 0.05
    fi
fi

# 4. Capture d'état, basculement vers workspaces réservés et expulsion des fenêtres
python3 -B "$HELPER_SCRIPT" save >/dev/null 2>&1
python3 -B "$HELPER_SCRIPT" switch-reserved >/dev/null 2>&1
python3 -B "$HELPER_SCRIPT" expel-clients >/dev/null 2>&1

# 5. Démarrer le watcher d'événements et hotplug en tâche de fond
python3 -B "$HELPER_SCRIPT" watch 9>&- &
WATCHER_PID=$!

# 6. Affichage du verrou Hyprlock sous inhibiteur sleep:idle (veille PC et écran noir désactivés sous verrou)
hyprctl dispatch dpms on >/dev/null 2>&1 || true
command -v brightnessctl >/dev/null && brightnessctl -r >/dev/null 2>&1 || true
if command -v systemd-inhibit >/dev/null 2>&1; then
    systemd-inhibit --what=sleep:idle --who="Aurora Lock" \
        --why="Session verrouillée : veille PC et écran noir désactivés" \
        --mode=block hyprlock 9>&-
else
    hyprlock 9>&-
fi

cleanup

