#!/usr/bin/env bash
# Script de capture d'écran Aurora pour Hyprland
# Supporte :
#   - area   (défaut) : sélection rectangulaire interactive via slurp (thème Aurora)
#   - screen          : capture plein écran du moniteur actif
#   - window          : capture de la fenêtre active

MODE="${1:-area}"
EDIT_MODE=0
if [ "$MODE" = "edit" ] || [ "${2:-}" = "edit" ] || [ "${2:-}" = "--edit" ]; then
    EDIT_MODE=1
    [ "$MODE" = "edit" ] && MODE="area"
fi

# Répertoire de destination (conforme XDG avec repli xdg-user-dir / Pictures / Images)
if [ -z "${XDG_PICTURES_DIR:-}" ] && command -v xdg-user-dir >/dev/null 2>&1; then
    XDG_PICTURES_DIR="$(xdg-user-dir PICTURES 2>/dev/null || true)"
fi
if [ -z "${XDG_PICTURES_DIR:-}" ]; then
    if [ -d "$HOME/Images" ]; then
        XDG_PICTURES_DIR="$HOME/Images"
    elif [ -d "$HOME/Pictures" ]; then
        XDG_PICTURES_DIR="$HOME/Pictures"
    else
        XDG_PICTURES_DIR="$HOME/Images"
    fi
fi
SCREENSHOTS_DIR="${XDG_PICTURES_DIR%/}/Captures d’écran"
mkdir -p "$SCREENSHOTS_DIR"

FILENAME="Capture d’écran du $(date +'%Y-%m-%d %H-%M-%S').png"
FILEPATH="$SCREENSHOTS_DIR/$FILENAME"

case "$MODE" in
    window)
        # Récupération et bornage strict de la géométrie fenêtre dans le moniteur hôte
        MONITORS_JSON=$(hyprctl monitors -j 2>/dev/null || echo '[]')
        GEOM=$(hyprctl activewindow -j 2>/dev/null | jq -r --argjson mons "$MONITORS_JSON" '
            . as $w |
            ($mons | map(select(.id == $w.monitor)) | .[0]) as $m |
            if ($w.at == null or $w.size == null) then empty
            elif $m == null then
                "\([0, $w.at[0]] | max),\([0, $w.at[1]] | max) \([1, $w.size[0]] | max)x\([1, $w.size[1]] | max)"
            else
                ((if ($m.transform % 2) == 1 then ($m.height / $m.scale) else ($m.width / $m.scale) end) | floor) as $mw |
                ((if ($m.transform % 2) == 1 then ($m.width / $m.scale) else ($m.height / $m.scale) end) | floor) as $mh |
                ([$m.x, $w.at[0]] | max) as $x1 |
                ([$m.y, $w.at[1]] | max) as $y1 |
                ([$m.x + $mw, $w.at[0] + $w.size[0]] | min) as $x2 |
                ([$m.y + $mh, $w.at[1] + $w.size[1]] | min) as $y2 |
                if ($x2 > $x1 and $y2 > $y1) then "\($x1),\($y1) \($x2 - $x1)x\($y2 - $y1)" else empty end
            end' 2>/dev/null)
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
        # Gel instantané de l'affichage via hyprpicker (tous les moniteurs figés)
        PICKER_PID=""
        if command -v hyprpicker >/dev/null 2>&1; then
            hyprpicker -r -z &
            PICKER_PID=$!
            trap 'kill $PICKER_PID 2>/dev/null || true' EXIT INT TERM
            sleep 0.1
        fi

        # Sélection interactive avec charte graphique Aurora (Bordure fine 1px, pas de rémanence)
        GEOM=$(slurp -d -b '#0a0f1e66' -c '#00f0ffff' -s '#00f0ff1a' -w 1 2>/dev/null)
        SLURP_STATUS=$?

        # Capture immédiate de la zone sélectionnée pendant le gel
        if [ $SLURP_STATUS -eq 0 ] && [ -n "$GEOM" ]; then
            grim -g "$GEOM" "$FILEPATH"
        fi

        # Libération déterministe de l'écran (dégel)
        if [ -n "$PICKER_PID" ]; then
            kill "$PICKER_PID" 2>/dev/null || true
            wait "$PICKER_PID" 2>/dev/null || true
            trap - EXIT INT TERM
        fi

        if [ $SLURP_STATUS -ne 0 ] || [ -z "$GEOM" ]; then
            # Annulation par l'utilisateur (Escape ou clic droit)
            exit 0
        fi
        ;;
esac

# Vérifier que le fichier a bien été généré
if [ -f "$FILEPATH" ]; then
    # Copie immédiate dans le presse-papiers Wayland
    wl-copy --type image/png < "$FILEPATH"

    if [ "$EDIT_MODE" -eq 1 ]; then
        if command -v swappy >/dev/null 2>&1; then
            swappy -f "$FILEPATH"
        else
            # Bascule propre sur notification et presse-papier direct sans erreur
            notify-send \
                -a "Aurora Screenshot" \
                -i "$FILEPATH" \
                -t 3500 \
                "Capture d'écran effectuée" \
                "Enregistrée : $FILENAME\nCopiée dans le presse-papiers (swappy non installé)" 2>/dev/null
        fi
    else
        # Notification standard avec vignette de prévisualisation
        notify-send \
            -a "Aurora Screenshot" \
            -i "$FILEPATH" \
            -t 3000 \
            "Capture d'écran effectuée" \
            "Enregistrée : $FILENAME\nCopiée dans le presse-papiers" 2>/dev/null
    fi
fi
