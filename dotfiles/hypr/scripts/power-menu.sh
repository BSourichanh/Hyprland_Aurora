#!/usr/bin/env bash
# Menu d'alimentation et de session Aurora (Super + S)
# Toggle rapide et exécution directe

# 1. Si wofi est déjà ouvert, le fermer immédiatement (toggle)
if pgrep -x "wofi" > /dev/null; then
    pkill -x "wofi"
    exit 0
fi

# 2. Options du menu avec icônes
OPTS="  Verrouiller l'écran\n  Fermer la session\n  Mettre en veille\n  Redémarrer\n  Éteindre le PC"

# 3. Emplacement de la feuille de style Aurora
STYLE_FILE="$HOME/.config/wofi/style.css"
if [ ! -f "$STYLE_FILE" ]; then
    STYLE_FILE="$HOME/Documents/antigravity/hyprland_project/dotfiles/wofi/style.css"
fi

# 4. Afficher le menu Wofi dmenu centré
CHOICE=$(printf "%b\n" "$OPTS" | wofi --dmenu \
    --prompt "Session Aurora" \
    --width 340 \
    --height 280 \
    --location center \
    --style "$STYLE_FILE" \
    --insensitive 2>/dev/null)

# 5. Exécuter l'action sélectionnée
case "$CHOICE" in
    *"Verrouiller"*)
        "$HOME/.config/hypr/lock.sh"
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
