# Hyprland Configuration & Lock Protocol (`dotfiles/hypr/`) 🌌

Configuration modulaire pour le compositeur Wayland **Hyprland** (0.56.2), intégrant le design system *Hybrid Summer*, la gestion multi-écrans (`DP-1` et `DP-2`), les plugins graphiques et le protocole de verrouillage sécurisé.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/hypr/
├── hyprland.conf       # Configuration maîtresse (moniteurs, autostart, binds, layouts, règles)
├── hyprviz.conf        # Paramètres d'apparence harmonisés (rounding 17px, border 2px, dégradé néon)
├── hypridle.conf       # Démon d'inactivité (verrouillage 5 min, extinction écrans)
├── hyprlock.conf       # Interface de déverrouillage graphique (champ mot de passe néon, flou GPU)
├── lock.sh             # Script de verrouillage sécurisé avec Safe Cleanup Handler (RAII)
├── scripts/
│   ├── reload.sh       # Script de rechargement complet (Hyprland + Waybar + notification)
│   └── wofi-toggle.sh  # Lanceur d'applications Wofi avec backdrop transparent (wait -n, 0% CPU)
├── plugins/
│   ├── Hyprspace.so    # Plugin Mission Control / Workspace Overview (SUPER + TAB)
│   └── hyprglass.so    # Effets de flou glassmorphism avancé pour surfaces Wayland
└── theme-summer/
    └── wallpaper.jpg   # Fond d'écran statique haute définition de secours (swaybg)
```

---

## 🎨 Charte Visuelle Hyprland

- **Coins arrondis** : `rounding = 17` uniforme sur toutes les fenêtres et conteneurs.
- **Épaisseur de bordure** : `border_size = 2`.
- **Dégradé actif** : Angle 45° fluide (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`).
- **Inactif** : `rgba(7a8fae33)` discret sans halo parasite.

---

## 🔒 Protocole de Verrouillage Sécurisé (`lock.sh`)

Le script [`lock.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/lock.sh) garantit la confidentialité des espaces de travail et élimine les artefacts de capture :

1. **Isolation Multi-Écrans Préventive** :
   - Requête instantanée JSON (`hyprctl monitors -j | jq`).
   - Déplacement immédiat de chaque écran vers des espaces de travail temporaires vides (90, 91, etc.) pour masquer les fenêtres ouvertes avant toute capture.
2. **Synchronisation Anti-Course Screencopy** :
   - `hyprlock` effectue la capture d'écran via `screencopy` en seulement **32 ms**.
   - Masquage de Waybar via `killall -SIGUSR1 waybar` suivi d'un `sleep 0.15` **strictement obligatoire** pour laisser le temps au compositeur de démapper la barre avant la capture.
   - Fermeture forcée des popups flottants (`wofi`, carte Spotify).
3. **Restauration Déterministe (Pattern RAII)** :
   - Routine `cleanup()` enregistrée sur tous les signaux d'interruption (`trap ... EXIT INT TERM`).
   - Restauration en bloc des workspaces d'origine (`hyprctl --batch "$RESTORE_CMD"`) et réaffichage de Waybar.

---

## ⌨️ Raccourcis Clavier Définis

| Raccourci | Action |
| :--- | :--- |
| <kbd>SUPER</kbd> + <kbd>Return</kbd> / <kbd>SUPER</kbd> + <kbd>Q</kbd> | Lancer le terminal Kitty |
| <kbd>SUPER</kbd> + <kbd>C</kbd> | Fermer la fenêtre active |
| <kbd>SUPER</kbd> + <kbd>V</kbd> | Basculer la fenêtre en mode flottant |
| <kbd>SUPER</kbd> + <kbd>R</kbd> | Ouvrir / Fermer Wofi (`wofi-toggle.sh`) |
| <kbd>SUPER</kbd> + <kbd>E</kbd> | Gestionnaire de fichiers (Nautilus) |
| <kbd>SUPER</kbd> + <kbd>L</kbd> | Verrouillage immédiat (`lock.sh`) |
| <kbd>SUPER</kbd> + <kbd>TAB</kbd> | Vue d'ensemble Hyprspace (Mission Control) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>R</kbd> | Recharger la configuration (`hyprctl reload`) et relancer la barre (`hyprbar restart`) |
| <kbd>SUPER</kbd> + <kbd>&</kbd> à <kbd>à</kbd> (1-10) | Changer d'espace de travail actif |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>&</kbd> à <kbd>à</kbd> | Déplacer la fenêtre active vers l'espace de travail ciblé |

---

## ⚙️ Maintenance & Rechargement

```bash
# Recharger la configuration Hyprland à chaud
hyprctl reload

# Vérifier la syntaxe des scripts
bash -n dotfiles/hypr/lock.sh
bash -n dotfiles/hypr/scripts/wofi-toggle.sh
```
