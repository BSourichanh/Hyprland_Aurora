#!/usr/bin/env bash
# Bascule rapide et légère pour Wofi avec détection de clic extérieur événementielle (0% CPU)

# Si wofi est déjà ouvert, le fermer immédiatement (toggle)
if pgrep -x "wofi" > /dev/null; then
    pkill -x "wofi"
    pkill -x "slurp"
    exit 0
fi

# Nettoyer tout résidu précédent
pkill -x "slurp" 2>/dev/null

# 1. Lancer l'overlay transparent en arrière-plan pour capturer le clic extérieur
slurp -b '#00000000' -c '#00000000' -s '#00000000' >/dev/null 2>&1 &
SLURP_PID=$!

# 2. Lancer wofi au-dessus de l'overlay
wofi --show drun &
WOFI_PID=$!

# Filet de sécurité : garantir la mort des deux sous-processus quoi qu'il arrive
trap 'kill "$WOFI_PID" "$SLURP_PID" 2>/dev/null; wait "$WOFI_PID" "$SLURP_PID" 2>/dev/null' EXIT INT TERM

# 3. Attente événementielle au niveau noyau (zéro boucle active, zéro utilisation CPU)
wait -n "$WOFI_PID" "$SLURP_PID" 2>/dev/null
