#!/usr/bin/env bash

# Si wofi est déjà ouvert, le fermer immédiatement (toggle)
if pgrep -x "wofi" > /dev/null; then
    pkill -x "wofi"
    exit 0
fi

# Lancer wofi en arrière-plan
wofi --show drun &
WOFI_PID=$!

# Attendre un bref instant que wofi soit affiché
sleep 0.15

# Trouver le socket d'événements Hyprland
SOCK=$(find "$XDG_RUNTIME_DIR/hypr" -name ".socket2.sock" -print -quit 2>/dev/null)

if [ -n "$SOCK" ] && [ -S "$SOCK" ]; then
    # Surveiller les changements de focus de fenêtre, d'espace de travail ou de moniteur
    socat -u UNIX-CONNECT:"$SOCK" - 2>/dev/null | while read -r line; do
        case "$line" in
            "activewindow>>"*|"focusedmon>>"*|"workspace>>"*)
                kill "$WOFI_PID" 2>/dev/null
                break
                ;;
        esac
        # Quitter si wofi s'est fermé normalement (Entrée, Échap, etc.)
        if ! kill -0 "$WOFI_PID" 2>/dev/null; then
            break
        fi
    done
fi

wait "$WOFI_PID" 2>/dev/null
