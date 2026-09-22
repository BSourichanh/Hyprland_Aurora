#!/usr/bin/env bash
# Sélecteur graphique Wofi / CLI pour le moteur de rendu Lucy (GPU vs CPU)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TOOL="$PROJECT_DIR/scripts/wallpaper_tool.py"

if [ ! -f "$TOOL" ]; then
    TOOL="$HOME/Documents/antigravity/hyprland_project/scripts/wallpaper_tool.py"
fi

# Si un argument explicite est fourni en CLI (gpu ou cpu)
if [ -n "$1" ]; then
    TARGET="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
    if [ "$TARGET" = "gpu" ] || [ "$TARGET" = "cpu" ]; then
        python3 "$TOOL" renderer "$TARGET"
        if [ "$TARGET" = "gpu" ]; then
            notify-send "Aurora Lucy Wallpaper" "Moteur de rendu basculé sur GPU (Intel UHD 630)" -i video-display 2>/dev/null || true
        else
            notify-send "Aurora Lucy Wallpaper" "Moteur de rendu basculé sur CPU (Mesa LLVMpipe)" -i cpu 2>/dev/null || true
        fi
        exit 0
    else
        echo "Usage: $(basename "$0") [gpu|cpu]" >&2
        exit 1
    fi
fi

# Mode interactif Wofi
OPT_GPU="󰢮 GPU (Accélération Matérielle — Intel UHD 630)"
OPT_CPU="󰘚 CPU (Rendu Logiciel — Mesa LLVMpipe)"

CHOSEN=$(printf "%s\n%s\n" "$OPT_GPU" "$OPT_CPU" | wofi --dmenu --prompt "Rendu Lucy :" --width 480 --lines 3 2>/dev/null)

case "$CHOSEN" in
    *"GPU"*)
        python3 "$TOOL" renderer gpu
        notify-send "Aurora Lucy Wallpaper" "Moteur de rendu basculé sur GPU (Intel UHD 630)" -i video-display 2>/dev/null || true
        ;;
    *"CPU"*)
        python3 "$TOOL" renderer cpu
        notify-send "Aurora Lucy Wallpaper" "Moteur de rendu basculé sur CPU (Mesa LLVMpipe)" -i cpu 2>/dev/null || true
        ;;
    *)
        exit 0
        ;;
esac
