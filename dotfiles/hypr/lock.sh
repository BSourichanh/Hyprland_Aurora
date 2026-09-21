#!/bin/bash
# Empêcher le lancement si hyprlock tourne déjà
if pidof hyprlock >/dev/null; then
    exit 0
fi

SWITCH_CMD=""
RESTORE_CMD=""
FOCUSED_MON=""
WS_TEMP=98

# Récupérer l'état de tous les moniteurs en une seule extraction jq (zéro sous-processus répété)
while read -r MON_NAME MON_WS IS_FOCUSED; do
    [ -z "$MON_NAME" ] && continue
    if [ "$IS_FOCUSED" = "true" ]; then
        FOCUSED_MON="$MON_NAME"
    fi
    SWITCH_CMD="${SWITCH_CMD}dispatch focusmonitor ${MON_NAME}; dispatch workspace ${WS_TEMP}; "
    RESTORE_CMD="${RESTORE_CMD}dispatch focusmonitor ${MON_NAME}; dispatch workspace ${MON_WS}; "
    WS_TEMP=$((WS_TEMP + 1))
done < <(hyprctl monitors -j 2>/dev/null | jq -r '.[] | "\(.name) \(.activeWorkspace.id) \(.focused)"')

# Restaurer le moniteur actif après déverrouillage
if [ -n "$FOCUSED_MON" ]; then
    RESTORE_CMD="${RESTORE_CMD}dispatch focusmonitor ${FOCUSED_MON}; "
fi

# Basculer vers des espaces de travail temporaires vides (aucun écran ne montre de fenêtre)
if [ -n "$SWITCH_CMD" ]; then
    hyprctl --batch "$SWITCH_CMD" >/dev/null 2>&1
fi

# Fermer les menus et cartes popups potentiellement ouverts
pkill -x wofi 2>/dev/null
"$HOME/.config/waybar/scripts/spotify-card.py" hide >/dev/null 2>&1 &

# Masquer Waybar pendant le verrouillage et la restaurer au déverrouillage
WAYBAR_WAS_RUNNING=0
if pgrep -x waybar >/dev/null; then
    WAYBAR_WAS_RUNNING=1
    killall -SIGUSR1 waybar 2>/dev/null
    # Laisser le temps à Waybar et GTK de démapper la surface avant que hyprlock ne capture l'écran
    sleep 0.15
fi

# Gestionnaire de nettoyage déterministe (Safe Cleanup / RAII)
CLEANED=0
cleanup() {
    [ "$CLEANED" -eq 1 ] && return
    CLEANED=1

    # Restaurer instantanément tous les espaces de travail et fenêtres
    if [ -n "$RESTORE_CMD" ]; then
        hyprctl --batch "$RESTORE_CMD" >/dev/null 2>&1
    fi

    # Restaurer Waybar si elle était active
    if [ "$WAYBAR_WAS_RUNNING" -eq 1 ]; then
        killall -SIGUSR1 waybar 2>/dev/null
    fi
}

trap cleanup EXIT INT TERM

# Lancer l'écran de verrouillage
hyprlock

# Exécuter le nettoyage à la sortie normale
cleanup

