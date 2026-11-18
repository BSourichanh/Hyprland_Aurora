# Scripts & CLI d'Administration (`scripts/`) 🛠️

Boîte à outils centralisée pour l'administration de l'environnement Hyprland Aurora : gestion du moteur de fond d'écran natif Wayland `aurora-wallpaper`, thémage dynamique, serveur MCP (Model Context Protocol), audit d'intégrité des 42 hardlinks et intégration système.

---

## 📁 Contenu du Répertoire

```
scripts/
├── aurora_osd.py        # OSD natif GTK3 gtk-layer-shell (son, micro, Verr. Maj -> ~/.local/bin/aurora-osd)
├── hyprbar              # Gestionnaire CLI Waybar et carte Spotify (anti-fuite de processus)
├── wallpaper_tool.py    # CLI unifié d'administration du fond d'écran (status, mask, check-links, restart, daemon, ensure)
├── wallpaper_daemon.py  # Démon d'écoute IPC Hyprland (.socket2.sock) pour hotplug et réveil DPMS
├── theme_switcher.py    # Gestionnaire CLI de bascule de thèmes d'ambiance (apply, list, status)
├── theme_models.py      # Modèles de données et palettes des 4 thèmes (aurora, tokyo-night, blackwall-red, cyberpunk-amber)
├── theme_templates.py   # Générateurs vectoriels et CSS (bar-bg.svg, Waybar, Wofi, SwayNC, Kitty)
├── aurora_runtime.py    # Gestion sécurisée de $AURORA_RUNTIME_DIR (0700) et mutex atomiques (flock 0600)
├── aurora_mcp_server.py # Micro-serveur FastMCP Aurora (13 outils réels, modes serve/status/audit/reload)
├── aurora_mcp/          # Outils modulaires du serveur MCP (system_tools.py, media_tools.py)
├── verify_aurora.sh     # Harnais unifié de preuves et validation zéro-régression (supporte --read-only)
└── setup/               # Modules d'installation du système (packages.sh, compile.sh, hardlinks.sh)
    └── packages.sh      # Dépendances système et intégration Nautilus (supporte --nautilus-only)
```

---

## 🚀 Utilitaires & Commandes CLI

### 1. Fond d'Écran & Maintenance (`wallpaper_tool.py`)

Le script `wallpaper_tool.py` s'exécute depuis la racine du dépôt :

```bash
# Surveillance du moteur aurora-wallpaper, PIDs, RAM (~72 Mo), CPU et couches Wayland
./scripts/wallpaper_tool.py status

# Régénération du masque Blackwall vectoriel haute fidélité (blackwall_mask.png)
./scripts/wallpaper_tool.py mask

# Audit d'intégrité physique des 42 hardlinks dotfiles <-> ~/.config/
./scripts/wallpaper_tool.py check-links

# Redémarrage propre du moteur aurora-wallpaper sous mutex sécurisé
./scripts/wallpaper_tool.py restart

# Lancement direct du démon hotplug IPC Hyprland
./scripts/wallpaper_tool.py daemon

# Maintien en condition opérationnelle (ensure) sur tous les écrans connectés
./scripts/wallpaper_tool.py ensure
```

### 2. Démon Hotplug & Événements IPC (`wallpaper_daemon.py`)

Supervise le socket événementiel Hyprland (`.socket2.sock`). Détecte instantanément les événements `monitoradded`, `monitorremoved`, `configreloaded` et les changements d'état DPMS.
- Applique une temporisation anti-rebond (*debounce* de 0.4s).
- Vérifie l'état de verrouillage via `$AURORA_RUNTIME_DIR/hypr_locked` avant ré-application.
- Exécuté automatiquement en arrière-plan via `dotfiles/hypr/scripts/wallpaper_daemon.sh` au démarrage d'Hyprland (`hl.on("hyprland.start")`).

### 3. Sélecteur de Thèmes Dynamique (`theme_switcher.py`)

Bascule instantanée d'ambiance visuelle sans rupture des hardlinks (`truncate()` + réécriture *in-place*) :

```bash
# Lister les thèmes disponibles (aurora, tokyo-night, blackwall-red, cyberpunk-amber)
python3 scripts/theme_switcher.py list

# Afficher l'état et la palette du thème actif
python3 scripts/theme_switcher.py status

# Appliquer un thème et synchroniser Waybar, Wofi, SwayNC, Kitty et Hyprland
python3 scripts/theme_switcher.py apply tokyo-night
```

### 4. Serveur MCP Aurora (`aurora_mcp_server.py`)

Serveur FastMCP exposant **13 outils réels** pour l'automatisation et le diagnostic :

```bash
# Mode stdio par défaut pour agents IA et assistants MCP
aurora-mcp serve

# Diagnostic consolidé en sortie JSON CLI
aurora-mcp status

# Audit d'intégrité physique des 42 hardlinks en sortie JSON CLI
aurora-mcp audit

# Rechargement unifié de l'environnement (Waybar, SwayNC, fonds, etc.)
aurora-mcp reload
```

#### Catalogue des 13 Outils MCP :
1. `get_aurora_status` : Diagnostic temps réel exhaustif (moteur EGL, PIDs, GPU, Waybar, SwayNC, Spotify, verrou, écrans, 42 hardlinks).
2. `system_tools.manage_wallpaper` : Pilotage du moteur de fond d'écran (`restart`, `ensure`, `status`).
3. `system_tools.manage_hyprbar` : Pilotage de Waybar (`restart`, `reload`, `toggle`, `status`).
4. `system_tools.lock_session` : Déclenchement du protocole de verrouillage sécurisé.
5. `system_tools.reload_all` : Rechargement global de tous les composants de session.
6. `system_tools.audit_hardlinks` : Audit physique strict des 42 hardlinks individuels.
7. `system_tools.wofi_launch` : Lancement contrôlé de Wofi (mode `drun` ou `power`).
8. `system_tools.compact_workspaces` : Déclenchement de l'auto-compactage multi-écrans des espaces.
9. `system_tools.switch_theme` : Bascule de thème d'ambiance visuelle via `theme_switcher`.
10. `media_tools.manage_swaync` : Contrôle du volet SwayNC (`toggle`, `dnd_toggle`, `clear_all`).
11. `media_tools.manage_blacklist` : Gestion de la liste noire de notifications SwayNC.
12. `media_tools.audio_control` : Réglage du volume et coupure audio (PipeWire / WirePlumber).
13. `media_tools.spotify_control` : Pilotage du lecteur Spotify via MPRIS D-Bus.

*(Note : L'ancien outil `renderer` obsolète a été retiré du catalogue).*

### 5. Validation Zéro-Régression (`verify_aurora.sh`)

Harnais de test unifié validant en 8 étapes la conformité complète du système :
```bash
# Validation complète en mode lecture seule (n'invoque pas l'étape mutante aurora-mcp reload)
./scripts/verify_aurora.sh --read-only

# Validation avec rechargement complet de la session live
./scripts/verify_aurora.sh
```

### 6. Déploiement & Paquets Système (`setup/packages.sh`)

Gère l'installation des dépendances et l'intégration Nautilus :
```bash
# Installation complète des dépendances système (apt / pacman) et de Nautilus
bash scripts/setup/packages.sh

# Configuration exclusive de l'extension Nautilus (clic droit -> Kitty, sans sudo)
bash scripts/setup/packages.sh --nautilus-only
```

---

## 🔒 Contrat de Sécurité `$AURORA_RUNTIME_DIR`

Tous les démons et scripts d'administration partagent l'arborescence runtime sécurisée :
- **Chemin canonique** : `${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora`
- **Permissions strictes** : Répertoire en mode `0700`, fichiers d'état et verrous en mode `0600`.
- **Verrous & Fichiers d'état gérés** :
  - `hypr_locked` : Drapeau de verrouillage de session actif.
  - `hypr_lock_instance.lock` : Mutex exclusif d'instance `hyprlock`.
  - `hypr_lock_orig_workspaces.json` : Sauvegarde des espaces de travail avant verrouillage.
  - `waybar_gpu.lock` / `waybar_gpu.json` : Mutex et cache partagé Leader-Follower DRM GPU.
  - `autocompact.lock` : Mutex de synchronisation de l'auto-compactage.
  - `spotify_card.sock` / `spotify_card.lock` / `spotify_covers/` : Socket IPC, verrou et jaquettes Spotify.
  - `wallpaper_daemon.lock` : Mutex singleton du démon de fond d'écran.

---

## 🏛️ Architecture & Bonnes Pratiques

- **Single-Pass GLSL & FBO Partagé** : Rendu exécuté 1 seule fois dans un buffer hors-écran $1920 \times 1080$, blitté simultanément sur chaque écran à 30 FPS (33 ms) en session normale (~72 Mo RAM sous EGL natif) et maintenu à 60 FPS (16 ms) sous verrouillage (choix utilisateur, au lieu de 1 FPS).
- **Gestionnaire RAII & Mutex Sécurisés** : Utilisation stricte de verrous non-bloquants `flock` libérés déterministement (`try...finally`) prévenant tout interblocage.
- **Zéro Polling** : Événements IPC socket UNIX Hyprland captés par `select()` non-bloquant.
- **Intégrité des 42 Hardlinks** : Écriture systématique *in-place* préservant rigoureusement les numéros d'inodes entre le dépôt et `~/.config/`.
