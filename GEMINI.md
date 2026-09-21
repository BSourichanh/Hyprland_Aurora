# Instructions de Projet & Directives de Développement — Hyprland / Hybrid Summer

Ce fichier définit le contexte technique, la charte graphique stricte, les règles d'architecture et les consignes d'optimisation pour l'environnement Hyprland et ses composants (Waybar, Wofi, Spotify Card, Kitty).

---

## ⚡ Directives d'Optimisation de Tokens & Concision

1. **Concision Maximale** :
   - Pas de politesses superflues ni d'introductions verbeuses.
   - Réponses directes, denses, orientées action (code ciblé, explications en puces courtes).
   - Privilégier les remplacements ciblés (`replace_file_content`) plutôt que de réécrire des fichiers volumineux complets.
2. **Gestion du Contexte & Outils** :
   - Cibler la lecture des fichiers aux lignes nécessaires.
   - Utiliser des filtres de commande (`grep`, `jq`, flags silencieux) pour éviter les sorties trop longues.
3. **Langue** : Français technique, précis et direct.

---

## 🎨 Charte Graphique & Design System (Hybrid Summer Theme)

Tous les composants de l'interface doivent rigoureusement respecter ces constantes :

### 1. Palette de Couleurs Néon
- **Cyan lumineux (primaire)** : `#00f0ff` / `rgba(0, 240, 255, 1.0)`
- **Bleu Tokyo Night (secondaire)** : `#7aa2f7`
- **Violet néon (accent)** : `#9778d0`
- **Rose / Rouge (actions Liker / alertes)** : `#f43f5e` / `#f87171`
- **Fonds translucides** :
  - Barre principale (`hyprbar`) : `rgba(10, 15, 30, 0.20)` (effet verre fumé ultra-léger avec flou de composition).
  - Modules internes, popup et menus : `rgba(10, 15, 30, 0.65)` à `rgba(10, 15, 30, 0.85)`.

### 2. Géométrie & Bordures
- **Rayon d'angle (Rounding)** : **`17px`** obligatoire sur tous les conteneurs (fenêtres Hyprland, Hyprbar, popup Spotify, Wofi, champ de saisie Hyprlock).
- **Épaisseur de bordure** : **`2px`** uniforme sur tout l'environnement (`border_size = 2` dans `hyprland.conf` et `hyprviz.conf`).
- **Dégradé vectoriel continu** : Angle 45° ou 135° avec transition fluide (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`).

### 3. Règles Critiques GTK3 CSS (Waybar & Wofi)
- ⚠️ **Ne jamais utiliser `border-image`** : Le moteur CSS de GTK3 désactive `border-radius` dès qu'un `border-image` est présent (angles coupés à 90°).
- **Pour les modules / capsules internes** : Utiliser le double `background-image` avec `background-clip: padding-box, border-box` et `border: 2px solid transparent`.
- **Pour la barre translucide (`window#waybar`)** : Utiliser impérativement le calque SVG vectoriel [bar-bg.svg](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/waybar/bar-bg.svg) avec `stroke="url(#grad)" stroke-width="2"`, dimensions 1900x34 et `rx="16" ry="16"`. Ne jamais appliquer un dégradé direct CSS sur la barre sous peine de saignement opaque.

---

## 🖥️ Règles d'Affichage Multi-Écrans & Workspaces

1. **Séparation Stricte par Moniteur** :
   - `all-outputs: false` dans `hyprland/workspaces`.
   - Pas de `persistent-workspaces` forcé pour laisser les espaces inactifs se masquer automatiquement.
   - Les espaces vides n'apparaissent jamais sur la barre ; ils apparaissent dynamiquement dès qu'une fenêtre y est créée et disparaissent dès qu'ils sont vidés.
2. **Hiérarchie Visuelle des 3 États de Workspace** :
   - **Focus Actif (`#workspaces button.active`)** : Plein dégradé néon 45° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`), texte sombre contrasté `#090727`, ombre portée néon cyan (`box-shadow: 0 0 10px rgba(0, 240, 255, 0.55)`).
   - **Affiché à l'Écran (`#workspaces button.visible`)** : Capsule avec bordure cyan 1.5px (`rgba(0, 240, 255, 0.65)`), fond translucide teinté cyan (`rgba(0, 240, 255, 0.15)`), texte cyan `#00f0ff`, lueur douce. Permet de savoir instantanément quel espace est visible sur l'écran secondaire non focus.
   - **Arrière-plan Inactif (`#workspaces button`)** : Texte discret bleu-gris `#7a8fae`, fond et bordure transparents (surbrillance `#00f0ff` au survol).

---

## 🎵 Architecture du Mini-Player Spotify & Règle Anti-Capsule Fantôme

1. **Assemblage Continu Sans Espacement** :
   - Le groupe `group/spotify-player` doit obligatoirement avoir `"spacing": 0`.
   - Modules enfants ordonnés : `mpris`, `custom/spotify-prev`, `custom/spotify-play-pause`, `custom/spotify-next`.
2. **Zéro-Bordure sur le Conteneur Parent** :
   - Le conteneur parent `#spotify-player` doit impérativement avoir :
     ```css
     #spotify-player { border: none; background: transparent; padding: 0; margin: 0; }
     ```
   - Waybar ne masquant pas automatiquement les `GtkBox` de type `group`, toute bordure ou padding mis sur `#spotify-player` laisserait une capsule vide résiduelle `[ ]` lorsque Spotify est arrêté.
3. **Fusion Vectorielle des Enfants** :
   - `#mpris` : arrondi gauche `10px 0 0 10px`, bordure gauche/haut/bas, padding gauche 12px.
   - Contrôles intermédiaires (`prev`, `play-pause`) : bordure haut/bas, sans bordure latérale.
   - `#custom-spotify-next` : arrondi droit `0 10px 10px 0`, bordure droite/haut/bas, padding droit 12px.
   - Dès que Spotify s'arrête, chaque enfant émet `""` / `"format-stopped": ""` et Waybar appelle `widget.hide()`. Le conteneur s'effondre à 0px sans laisser le moindre pixel à l'écran.

---

## 🔒 Protocole de Verrouillage Sécurisé (`lock.sh`)

1. **Synchronisation Anti-Course Décomposition / Screencopy** :
   - `hyprlock` effectue sa capture d'écran initiale via `screencopy` en seulement **32 ms**.
   - Après l'envoi de `killall -SIGUSR1 waybar`, un délai `sleep 0.15` est **strictement obligatoire** pour permettre au compositeur Wayland et à GTK de démapper la surface Waybar avant la capture.
   - Sans ce délai, Waybar est capturée dans l'image figée d'arrière-plan de `hyprlock`.
2. **Fermeture Préventive des Popups** :
   - Tout script de verrouillage doit fermer préventivement les couches flottantes :
     ```bash
     pkill -x wofi 2>/dev/null
     "$HOME/.config/waybar/scripts/spotify-card.py" hide >/dev/null 2>&1 &
     ```
3. **Restauration Déterministe** :
   - Restaurer l'affichage de Waybar via `trap '[ "$WAYBAR_WAS_RUNNING" -eq 1 ] && killall -SIGUSR1 waybar' EXIT INT TERM`.
   - Restaurer les espaces de travail initiaux via `hyprctl --batch "$RESTORE_CMD"`.

---

## 🖼️ Linux Wallpaper Engine & Gestion Multi-Écrans

1. **Architecture Multi-Processus (Résolution de l'Écran Blanc Wayland)** :
   - Sous Wayland / Hyprland, grouper plusieurs moniteurs sous un même processus (`linux-wallpaperengine --screen-root DP-1 --screen-root DP-2`) provoque l'affichage d'un écran blanc sur les écrans secondaires suite à des conflits de contextes EGL/OpenGL.
   - **Correction appliquée** : Patch direct dans `/usr/lib/linux-wallpaper-engine/resources/app.asar` (sauvegardé sous `.bak`). La méthode `spawnForScreens` découpe désormais toute liste d'écrans en processus indépendants dédiés (1 processus distinct par écran `DP-1` et `DP-2`).
2. **Hiérarchie des Couches Wayland (Layer Shell)** :
   - **Layer 0 (`background`)** : `swaybg` affiche instantanément le fond statique (`wallpaper.jpg`) au boot en ~10 ms (évite tout écran noir et sert de fallback résilient).
   - **Layer 1 (`bottom`)** : `linux-wallpaperengine` superpose son rendu animé directement au-dessus de `swaybg`.
   - **Layers 2 & 3 (`top` / `overlay`)** : `waybar` et les fenêtres restent prioritaires au premier plan.
3. **Protocole de Démarrage Automatique (Autostart)** :
   - Hyprland n'exécute pas les fichiers standards de `~/.config/autostart/`.
   - L'activation est orchestrée dans [`hyprland.conf`](file:///home/user/.config/hypr/hyprland.conf#L31-L35) :
     ```ini
     exec-once = swaybg -i /home/user/.config/hypr/theme-summer/wallpaper.jpg
     exec-once = linux-wallpaper-engine
     ```
   - **Mode Silencieux / Systray** : Dans [`~/.config/Linux Wallpaper Engine/settings.json`](file:///home/user/.config/Linux%20Wallpaper%20Engine/settings.json), `"minimizeOnStartup": true` est activé avec `"enableSystemTray": true`. L'application se loge directement dans la zone de notification Waybar sans ouvrir de fenêtre intempestive au login, et restaure automatiquement le dernier fond d'écran configuré dans [`active-wallpapers.json`](file:///home/user/.config/Linux%20Wallpaper%20Engine/active-wallpapers.json).

---

## ⚡ Shaders & Customisation du Thème Lucy (`3566437475`)

1. **Arborescence & Dépaquetage du Workshop** :
   - Emplacement : `/home/user/.steam/steam/steamapps/workshop/content/431960/3566437475/`
   - Archive originale préservée : `scene.pkg.orig`.
   - Scène décompressée pour modification à chaud des shaders, matériaux et passes de rendu.
2. **Correction Colorimétrique & Surexposition (`scene.json`)** :
   - Sous OpenGL / Linux, la passe `edge_glow` (id 698) causait une saturation totale (visage entièrement blanc). Elle a été désactivée (`"visible": false`).
   - L'intensité de la passe `shine` (id 427) a été diminuée pour restaurer le piqué, les contrastes et les ombres profondes d'origine du personnage.
3. **Rework du Shader Glitch (`shake.frag`)** :
   - Fichier : [`shaders/workshop/2125458920/effects/shake.frag`](file:///home/user/.steam/steam/steamapps/workshop/content/431960/3566437475/shaders/workshop/2125458920/effects/shake.frag)
   - **Déplacement Géométrique Pur (Zéro Décoloration)** :
     - ❌ **Aberration chromatique supprimée** : Élimination du décalage RVB baveux.
     - ❌ **Teintes parasites supprimées** : Retrait des flashs artificiels jaune Relic et cyan ainsi que des scanlines assombrissantes.
     - Échantillonnage direct `texSample2D(g_Texture0, glitchUV)` garantissant une fidélité chromatique absolue à l'illustration.
   - **Slice Jitter Multi-Échelles à 3 Niveaux** :
     - **Niveau 1 (Tranches partielles)** : Segments horizontaux de largeurs aléatoires (12% à 57% de l'écran avec gestion du wrap) ne traversant pas brutalement toute la largeur.
     - **Niveau 2 (Blocs rectangulaires 2D)** : Découpage en grille $14 \times 32$ avec décalages $X$ et $Y$ indépendants simulant la corruption de paquets de mémoire.
     - **Niveau 3 (Micro-bandes)** : Lignes ultra-fines (hauteur 1/140e, largeur 3% à 18%) pour les saccades haute fréquence.
   - **Rythme Temporel** : Cycle de 3.6s avec impulsion `smoothstep` (3.1s à 3.55s) et micro-saccades pseudo-aléatoires (`hash11`).
4. **Dossier de Ressources Dédié (`ressource/`)** :
   - Dossier miroir sous `hyprland_project/ressource/` (et alias `resources/`) :
     - `lucy.png` : Artwork maître haute résolution $1920 \times 1080$ extrait sans perte du conteneur binaire `TEXV0005`.
     - `lucy_model.json` & `lucy_material.json` : Descripteurs de modèle et matériau Wallpaper Engine.
     - `lucy.tex` : Conteneur de texture binaire d'origine.
     - `preview.gif` : Vignette animée officielle.

---

## 🏛️ Architecture & Correspondance Système (`~/.config/`)

```
hyprland_project/
├── dotfiles/
│   ├── hypr/                 # Hyprland (0.56.2), hypridle, hyprlock, lock.sh, wofi-toggle.sh
│   ├── waybar/               # Config Waybar, style.css, bar-bg.svg, scripts Spotify
│   ├── wofi/                 # Configuration et CSS du lanceur d'applications
│   └── kitty/                # Terminal Kitty (transparence 0.85, palette Tokyo Night)
├── linux-wallpaperengine/     # Dépôt source / utilitaires du moteur Wallpaper Engine
├── ressource/                # Modèle, textures et assets graphiques de Lucy (Cyberpunk)
├── GEMINI.md                 # Directives d'architecture et consignes projet
└── README.md                 # Documentation générale
```

Les fichiers sous `dotfiles/` partagent les mêmes inodes (hard links) avec `~/.config/` :
- `~/.config/hypr/` ➔ `dotfiles/hypr/`
- `~/.config/waybar/` ➔ `dotfiles/waybar/`
- `~/.config/wofi/` ➔ `dotfiles/wofi/`
- `~/.config/kitty/` ➔ `dotfiles/kitty/`

*Vérification d'intégrité des liens* : toujours s'assurer que les inodes restent identiques (`ls -lai dotfiles/... ~/.config/...`). Ne jamais casser les hard links lors des écritures.

---

## ⚙️ Principes de Performance & Développement

1. **Événementiel Prioritaire (Zéro Polling Actif)** :
   - Préférer les signaux D-Bus MPRIS (`PropertiesChanged`) pour Spotify.
   - Utiliser `wait -n` au niveau noyau pour synchroniser les processus (`wofi-toggle.sh`) plutôt que des boucles `while sleep`.
2. **Mémoïsation & Caching** :
   - Socket IPC Hyprland : Stocker le chemin découvert dans `_cached_hypr_sock`.
   - Adresses mémoires des fenêtres : Mémoïser l'adresse `0x...` de la carte flottante Spotify pour un repositionnement direct en `< 1 ms` sans appeler `hyprctl clients -j`.
   - Pochette Spotify : Vérifier `loaded_cover_url` en mémoire vive avant tout accès disque.
   - D-Bus : Réutiliser le singleton `get_session_bus()`.
3. **Gestion des Processus** :
   - Toujours respecter le verrou singleton (`/tmp/spotify_card.lock`) pour le daemon Spotify afin d'éviter tout doublon.
   - Nettoyer systématiquement les processus fils avec des gestionnaires `trap ... EXIT INT TERM`.

---

## 🧪 Commandes de Référence Rapide

```bash
# Gestion de la barre et de la carte Spotify
hyprbar restart   # Redémarrage complet propre de Waybar et du daemon spotify-card
hyprbar reload    # Rechargement à chaud du style CSS (SIGUSR2)
hyprbar toggle    # Basculer affichage/masquage de la barre (SIGUSR1)
hyprbar status    # Afficher les PIDs et l'état

# Rechargement Hyprland
hyprctl reload    # Appliquer les modifications de hyprland.conf et hyprviz.conf

# Wallpaper Engine & Arrière-plans
pgrep -fl "linux-wallpaper"                # Vérifier les processus actifs et moniteurs associés
hyprctl layers | grep -A 5 "Layer level"   # Vérifier l'ordre des couches (swaybg = 0, wallpaper = 1, waybar = 2)
pkill -f linux-wallpaperengine             # Arrêter le moteur de rendu dynamique
linux-wallpaper-engine                     # Lancer le gestionnaire en arrière-plan (systray)

# Tests & Validation
bash -n dotfiles/hypr/scripts/wofi-toggle.sh
bash -n dotfiles/hypr/lock.sh
python3 -m py_compile dotfiles/waybar/scripts/spotify-card.py
python3 -m py_compile dotfiles/waybar/scripts/spotify.py
python3 -c "import json; json.load(open('dotfiles/waybar/config.jsonc'))"

# Vérification des hard links
ls -lai dotfiles/waybar/style.css ~/.config/waybar/style.css
ls -lai dotfiles/waybar/config.jsonc ~/.config/waybar/config.jsonc
ls -lai dotfiles/hypr/lock.sh ~/.config/hypr/lock.sh
```
