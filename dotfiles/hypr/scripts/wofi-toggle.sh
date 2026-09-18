#!/usr/bin/env bash

# Si wofi est déjà ouvert, le fermer immédiatement (toggle)
if pgrep -x "wofi" > /dev/null; then
    pkill -x "wofi"
    pkill -x "slurp"
    exit 0
fi

# Nettoyer tout slurp orphelin
pkill -x "slurp" 2>/dev/null

# 1. Lancer l'overlay transparent en arrière-plan pour capturer le clic extérieur
slurp -b '#00000000' -c '#00000000' -s '#00000000' >/dev/null 2>&1 &
SLURP_PID=$!

# 2. Lancer wofi au-dessus de l'overlay
wofi --show drun &
WOFI_PID=$!

# 3. Boucle de surveillance active
while true; do
    # Si wofi s'est fermé normalement (lancement d'appli ou Échap)
    if ! kill -0 "$WOFI_PID" 2>/dev/null; then
        kill "$SLURP_PID" 2>/dev/null
        break
    fi

    # Si slurp s'est arrêté (clic détecté en dehors de wofi)
    if ! kill -0 "$SLURP_PID" 2>/dev/null; then
        kill "$WOFI_PID" 2>/dev/null
        break
    fi

    sleep 0.05
done

wait "$WOFI_PID" 2>/dev/null
wait "$SLURP_PID" 2>/dev/null
