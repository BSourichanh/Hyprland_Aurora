#!/bin/bash
# Empêcher le lancement si hyprlock tourne déjà
if pidof hyprlock >/dev/null; then
    exit 0
fi

# Récupérer l'état des moniteurs au format JSON
MONITORS_JSON=$(hyprctl monitors -j 2>/dev/null)
FOCUSED_MON=$(echo "$MONITORS_JSON" | jq -r '.[] | select(.focused == true) | .name')

SWITCH_CMD=""
RESTORE_CMD=""
WS_TEMP=98

for row in $(echo "$MONITORS_JSON" | jq -r '.[] | @base64'); do
    _jq() {
        echo "${row}" | base64 --decode | jq -r "${1}"
    }
    MON_NAME=$(_jq '.name')
    MON_WS=$(_jq '.activeWorkspace.id')

    SWITCH_CMD="${SWITCH_CMD}dispatch focusmonitor ${MON_NAME}; dispatch workspace ${WS_TEMP}; "
    RESTORE_CMD="${RESTORE_CMD}dispatch focusmonitor ${MON_NAME}; dispatch workspace ${MON_WS}; "
    WS_TEMP=$((WS_TEMP + 1))
done

# Restaurer le moniteur actif après déverrouillage
if [ -n "$FOCUSED_MON" ]; then
    RESTORE_CMD="${RESTORE_CMD}dispatch focusmonitor ${FOCUSED_MON}; "
fi

# Basculer vers des espaces de travail vides (aucun écran ne montre de fenêtre)
if [ -n "$SWITCH_CMD" ]; then
    hyprctl --batch "$SWITCH_CMD" >/dev/null 2>&1
fi

# Lancer l'écran de verrouillage
hyprlock

# Restaurer instantanément tous les espaces de travail et fenêtres
if [ -n "$RESTORE_CMD" ]; then
    hyprctl --batch "$RESTORE_CMD" >/dev/null 2>&1
fi
