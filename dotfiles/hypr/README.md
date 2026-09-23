# Hyprland Configuration & Lock Protocol (`dotfiles/hypr/`) 🌌

Configuration modulaire pour le compositeur Wayland **Hyprland** (0.56.2), intégrant le design system **Aurora** (autonome et sur-mesure, détaché de son inspiration originelle Hybrid Summer), la gestion multi-écrans (`DP-1` et `DP-2`), les plugins graphiques et le protocole de verrouillage sécurisé.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/hypr/
├── hyprland.conf       # Configuration maîtresse (moniteurs, autostart, binds, layouts, règles)
├── hyprviz.conf        # Paramètres d'apparence harmonisés (rounding 17px, border 2px, dégradé néon)
├── hypridle.conf       # Démon d'inactivité (verrouillage 5 min, extinction écrans)
├── hyprlock.conf       # Interface de déverrouillage graphique (champ mot de passe néon, flou GPU)
├── lock.sh             # Script de verrouillage sécurisé avec Safe Cleanup Handler (RAII)
├── wallpaper_renderer.json # Persistance du moteur Lucy actif (GPU/CPU) et des FPS (60/20)
├── wallpaper-renderer.desktop # Lanceur d'applications Wofi pour le sélecteur
├── scripts/
│   ├── power-menu.sh   # Menu de session et d'alimentation Aurora (SUPER + S)
│   ├── screenshot.sh   # Outil de capture d'écran polyvalent (Print Screen, sélection, écran, fenêtre)
│   ├── wallpaper-select-renderer.sh # Sélecteur graphique Wofi GPU (60 FPS) / CPU (20 FPS)
│   ├── reload.sh       # Script de rechargement complet (Hyprland + Waybar + notification)
│   └── wofi-toggle.sh  # Lanceur d'applications Wofi avec backdrop transparent (wait -n, 0% CPU)
├── plugins/
│   ├── Hyprspace.so                  # Plugin Mission Control / Workspace Overview (SUPER + TAB)
│   ├── hyprspace-multimonitor.patch  # Correctif d'isolation stricte multi-écrans Hyprspace
│   └── hyprglass.so                  # Effets de flou glassmorphism avancé pour surfaces Wayland
└── theme-summer/
    └── wallpaper.jpg                 # Fond d'écran statique haute définition de secours (swaybg)
```

---

## 🎨 Charte Visuelle Hyprland

- **Coins arrondis** : `rounding = 17` uniforme sur toutes les fenêtres et conteneurs.
- **Épaisseur de bordure** : `border_size = 2`.
- **Dégradé actif animé** : Boucle vectorielle continue 360° sans coupure (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0` ➔ `#00f0ff`), rotation matérielle GPU (`animation = borderangle, 1, 50, linear, loop`).
- **Inactif** : `rgba(04404aaa)` discret sans halo parasite.

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

## ⚡ Menu de Session & Alimentation (`power-menu.sh`)

Le script [`power-menu.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/power-menu.sh) déploie une boîte de dialogue d'actions rapide :
- **Raccourci** : <kbd>SUPER</kbd> + <kbd>S</kbd> (toggle : un second appui ou <kbd>Échap</kbd> referme le menu).
- **Feuille de style dédiée** : [`dotfiles/wofi/power-menu.css`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/wofi/power-menu.css) sans barre de recherche (`hide_search=true` et `#input` réduit à 0px), avec 5 capsules de verre tactiles (Verrouiller, Fermer la session, Mettre en veille, Redémarrer, Éteindre).
- **Format compact** : $300 \times 265\text{ px}$ centré à l'écran, navigation clavier ou souris.

---

## 📸 Outil de Capture d'Écran Aurora (`screenshot.sh`)

Le script [`screenshot.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/screenshot.sh) gère les captures d'écran sous Wayland :
- **Réticule Aurora thémé** : `slurp` configuré avec bordure cyan néon 2px (`#00f0ff`), fond sombre Tokyo Night et lueur douce.
- **Modes pris en charge** :
  - `area` (défaut) : Sélection interactive rectangulaire (<kbd>Print</kbd> ou <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd>).
  - `screen` : Moniteur actif sous le curseur (<kbd>SHIFT</kbd> + <kbd>Print</kbd>).
  - `window` : Fenêtre sous focus actif (<kbd>SUPER</kbd> + <kbd>Print</kbd>).
  - `full` : Intégralité des écrans réunis (<kbd>CTRL</kbd> + <kbd>Print</kbd>).
- **Enregistrement & Presse-papiers** : Copie instantanée dans le presse-papiers via `wl-copy --type image/png`, sauvegarde dans `~/Images/Captures d’écran/Capture d’écran du AAAA-MM-JJ HH-MM-SS.png` et notification avec aperçu miniature (`notify-send`).

---

## ⌨️ Raccourcis Clavier Définis

| Raccourci | Action |
| :--- | :--- |
| <kbd>SUPER</kbd> + <kbd>Return</kbd> / <kbd>SUPER</kbd> + <kbd>Q</kbd> | Lancer le terminal Kitty |
| <kbd>SUPER</kbd> + <kbd>C</kbd> | Fermer la fenêtre active |
| <kbd>SUPER</kbd> + <kbd>V</kbd> | Basculer la fenêtre en mode flottant |
| <kbd>SUPER</kbd> + <kbd>R</kbd> | Ouvrir / Fermer Wofi (`wofi-toggle.sh`) |
| <kbd>SUPER</kbd> + <kbd>S</kbd> | Menu de session et alimentation (`power-menu.sh`) |
| <kbd>Impr écran</kbd> / <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd> | Capture d'écran (sélection rectangulaire Aurora) |
| <kbd>SHIFT</kbd> + <kbd>Impr écran</kbd> | Capture plein écran du moniteur actif |
| <kbd>SUPER</kbd> + <kbd>Impr écran</kbd> | Capture de la fenêtre active |
| <kbd>CTRL</kbd> + <kbd>Impr écran</kbd> | Capture intégrale (multi-écrans) |
| <kbd>SUPER</kbd> + <kbd>E</kbd> | Gestionnaire de fichiers (Nautilus) |
| <kbd>SUPER</kbd> + <kbd>L</kbd> | Verrouillage immédiat (`lock.sh`) |
| <kbd>SUPER</kbd> + <kbd>TAB</kbd> | Vue d'ensemble Hyprspace (Mission Control) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>R</kbd> | Recharger la configuration (`hyprctl reload`) et relancer la barre (`hyprbar restart`) |
| <kbd>SUPER</kbd> + <kbd>&</kbd> à <kbd>à</kbd> (1-10) | Changer d'espace de travail actif |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>&</kbd> à <kbd>à</kbd> | Déplacer la fenêtre active vers l'espace de travail ciblé |
| <kbd>SUPER</kbd> + <kbd>Molette Haut / Bas</kbd> | Défiler vers l'espace de travail précédent / suivant (`e-1` / `e+1`) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>Molette</kbd> | Déplacer la fenêtre active vers l'espace précédent / suivant |

---

## 🪟 Hyprspace Mission Control & Isolation Multi-Écrans

Le plugin Hyprspace fournit une vue d'ensemble exposé / Mission Control activable par <kbd>SUPER</kbd> + <kbd>TAB</kbd>.

Dans une configuration multi-moniteurs (`DP-2` à gauche, `DP-1` à droite) :
- **Problème d'origine** : Les workspaces inactifs ou vides fuitaient entre écrans (l'overview de l'écran droit affichait les workspaces 1 à 5 de l'écran gauche et vice versa).
- **Correctif natif C++ (`hyprspace-multimonitor.patch`)** :
  - Filtrage strict dans `src/Render.cpp` via `isWorkspaceForThisMonitor(wsID)`.
  - Résolution des liaisons configurées via `Config::workspaceRuleMgr()->getBoundMonitorStringForWS()`.
  - Bornes dynamiques calculées par moniteur via `getAllWorkspaceRules()`.
  - Nettoyage final garantissant que seuls les workspaces appartenant au moniteur actif sont affichés (1 à 5 sur `DP-2`, 6 à 10 sur `DP-1`).

---

## ⚙️ Maintenance & Rechargement

```bash
# Recharger la configuration Hyprland à chaud
hyprctl reload

# Vérifier la syntaxe des scripts
bash -n dotfiles/hypr/lock.sh
bash -n dotfiles/hypr/scripts/wofi-toggle.sh
```
