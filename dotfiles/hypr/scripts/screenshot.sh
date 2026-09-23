#!/usr/bin/env bash
# Script de capture d'écran Aurora pour Hyprland
# Supporte :
#   - area   (défaut) : sélection rectangulaire interactive via slurp (thème Aurora)
#   - screen          : capture plein écran du moniteur actif
#   - window          : capture de la fenêtre active

MODE="${1:-area}"

# Répertoire de destination (conforme XDG / existant)
SCREENSHOTS_DIR="${XDG_PICTURES_DIR:-$HOME/Images}/Captures d’écran"
mkdir -p "$SCREENSHOTS_DIR"

FILENAME="Capture d’écran du $(date +'%Y-%m-%d %H-%M-%S').png"
FILEPATH="$SCREENSHOTS_DIR/$FILENAME"

case "$MODE" in
    window)
        # Récupération géométrie fenêtre active Hyprland
        GEOM=$(hyprctl activewindow -j 2>/dev/null | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"' 2>/dev/null)
        if [ -z "$GEOM" ] || [ "$GEOM" = "null,null nullxnull" ]; then
            notify-send -t 2000 "Capture d'écran" "Aucune fenêtre active détectée" 2>/dev/null
            exit 1
        fi
        grim -g "$GEOM" "$FILEPATH"
        ;;
    screen)
        # Écran/moniteur actif sous le curseur
        FOCUSED_MONITOR=$(hyprctl monitors -j 2>/dev/null | jq -r '.[] | select(.focused) | .name' 2>/dev/null)
        if [ -n "$FOCUSED_MONITOR" ]; then
            grim -o "$FOCUSED_MONITOR" "$FILEPATH"
        else
            grim "$FILEPATH"
        fi
        ;;
    full)
        # Tous les moniteurs réunis
        grim "$FILEPATH"
        ;;
    area|*)
        # Sélection interactive avec charte graphique Aurora (Bordure cyan 2px, fond Tokyo Night)
        GEOM=$(slurp -d -b '#0a0f1e80' -c '#00f0ffff' -s '#00f0ff1a' -w 2 2>/dev/null)
        if [ -z "$GEOM" ]; then
            # Annulation par l'utilisateur (Escape ou clic droit)
            exit 0
        fi
        grim -g "$GEOM" "$FILEPATH"
        ;;
esac

# Vérifier que le fichier a bien été généré
if [ -f "$FILEPATH" ]; then
    # Copie dans le presse-papiers Wayland
    wl-copy --type image/png < "$FILEPATH"

    # Notification avec vignette de prévisualisation
    notify-send \
        -a "Aurora Screenshot" \
        -i "$FILEPATH" \
        -t 3000 \
        "Capture d'écran effectuée" \
        "Enregistrée : $FILENAME\nCopiée dans le presse-papiers" 2>/dev/null
fi
