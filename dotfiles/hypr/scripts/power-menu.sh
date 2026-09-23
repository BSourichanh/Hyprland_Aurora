#!/usr/bin/env bash
# Menu d'alimentation et de session Aurora (Super + S)
# Détection de clic extérieur événementielle (0% CPU) et bascule rapide (toggle)

# 1. Si wofi est déjà ouvert, le fermer immédiatement (toggle)
if pgrep -x "wofi" > /dev/null; then
    pkill -x "wofi"
    pkill -x "slurp"
    exit 0
fi

# Nettoyer tout résidu précédent
pkill -x "slurp" 2>/dev/null

# 2. Options du menu avec icônes FontAwesome
OPTS="  Verrouiller l'écran\n  Fermer la session\n  Mettre en veille\n  Redémarrer\n  Éteindre le PC"

# 3. Lancer l'overlay transparent en arrière-plan pour capturer le clic extérieur
slurp -b '#00000000' -c '#00000000' -s '#00000000' >/dev/null 2>&1 &
SLURP_PID=$!

(
    wait "$SLURP_PID" 2>/dev/null
    pkill -x "wofi" 2>/dev/null
) &
WATCHER_PID=$!

# Filet de sécurité : garantir l'arrêt des sous-processus
trap 'kill "$SLURP_PID" "$WATCHER_PID" 2>/dev/null; wait "$SLURP_PID" "$WATCHER_PID" 2>/dev/null' EXIT INT TERM

# 4. Afficher le menu Wofi dmenu centré
CHOICE=$(printf "%b\n" "$OPTS" | wofi --dmenu \
    --prompt "Session Aurora" \
    --width 360 \
    --lines 5 \
    --location center \
    --insensitive 2>/dev/null)

# Arrêter immédiatement l'overlay et le watcher
kill "$SLURP_PID" "$WATCHER_PID" 2>/dev/null

# 5. Exécuter l'action sélectionnée
case "$CHOICE" in
    *"Verrouiller"*)
        /home/user/.config/hypr/lock.sh
        ;;
    *"Fermer la session"*)
        hyprctl dispatch exit
        ;;
    *"Mettre en veille"*)
        systemctl suspend
        ;;
    *"Redémarrer"*)
        systemctl reboot
        ;;
    *"Éteindre"*)
        systemctl poweroff
        ;;
    *)
        exit 0
        ;;
esac
