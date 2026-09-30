# Scripts & CLI d'Administration (`scripts/`) 🛠️

Boîte à outils centralisée pour l'administration, le packaging binaire, la génération de masques vectoriels, la synchronisation du Workshop et l'audit d'intégrité de l'environnement Hyprland.

---

## 📁 Contenu du Répertoire

```
scripts/
└── wallpaper_tool.py    # CLI unifié d'administration (TEX, masquage, synchronisation, audit, processus)
```

---

## 🚀 Fonctionnalités du CLI `wallpaper_tool.py`

Le script est exécutable directement depuis la racine du dépôt :

### 1. Surveillance des Processus & Couches Wayland (`status`)
Affiche l'état des processus actifs de rendu dynamique, leurs moniteurs assignés (`DP-1`, `DP-2`) et l'empilement des calques Wayland rapporté par Hyprland :
```bash
./scripts/wallpaper_tool.py status
```
*Sortie type :*
```text
=== État des Processus Wallpaper Engine ===
  • PID 101351 : Moniteur [DP-1] (linux-wallpaperengine --screen-root DP-1 ...)
  • PID 101352 : Moniteur [DP-2] (linux-wallpaperengine --screen-root DP-2 ...)
✓ Total : 2 processus actif(s).

=== Couches Wayland Détectées (Hyprland) ===
  • DP-1 : Background:wallpaper[pid:3373] | Bottom:linux-wallpaperengine[pid:101351] | Top:waybar[pid:3378]
  • DP-2 : Background:wallpaper[pid:3373] | Bottom:linux-wallpaperengine[pid:101352] | Top:waybar[pid:3378]
```

### 2. Régénération du Masque Subpixel (`mask`)
Applique l'algorithme d'ensemencement universel ($D \le 1.8$), la propagation BFS ($D < 18.0$) et la préservation anatomique sur [`ressource/lucy.png`](file:///home/user/Documents/antigravity/hyprland_project/ressource/lucy.png), puis compile directement le conteneur binaire `blackwall_mask.tex` :
```bash
./scripts/wallpaper_tool.py mask
```

### 3. Packaging & Extraction Binaire TEX (`pack` / `unpack`)
Manipulation directe des conteneurs de textures Wallpaper Engine au format `TEXV0005` / `TEXB0004` (FIF_PNG) :
```bash
# Compresser un PNG vers un fichier .tex
./scripts/wallpaper_tool.py pack image.png image.tex --width 1920 --height 1080

# Extraire le PNG d'un conteneur .tex
./scripts/wallpaper_tool.py unpack image.tex image.png
```

### 4. Déploiement Steam Workshop (`sync`)
Synchronise les shaders Blackwall, les matériaux, le modèle, les textures et la configuration de scène (`scene.json`) vers le répertoire d'installation local Steam (`~/.steam/.../3566437475/`) :
```bash
./scripts/wallpaper_tool.py sync
```

### 5. Démarrage Sélectif Multi-Écrans (`ensure`)
Assure que le moteur de rendu tourne sur les écrans connectés, en ne démarrant une instance **que sur l'écran manquant** sans jamais interrompre ni redémarrer l'autre écran déjà actif. Vérifie la présence effective de la surface Wayland `Bottom` (`hyprctl layers -j`) et purge automatiquement les processus zombies :
```bash
# Vérifier et démarrer le fond d'écran uniquement sur les écrans connectés sans calque actif
./scripts/wallpaper_tool.py ensure

# Cibler un écran spécifique (ex. lors d'un événement de hotplug / réveil de DP-1)
./scripts/wallpaper_tool.py ensure DP-1
```

### 6. Redémarrage Multi-Écrans Déterministe (`restart`)
Relance les moteurs Wallpaper Engine en créant des sessions système découplées (`start_new_session=True`) pour chaque écran (`DP-1` et `DP-2`), protégé par un verrou mutex atomique (`flock` sur `/tmp/wallpaper_restart.lock`) contre les exécutions concurrentes :
```bash
# Redémarrage complet de tous les écrans connectés
./scripts/wallpaper_tool.py restart

# Redémarrer uniquement un écran spécifique (sans toucher l'autre)
./scripts/wallpaper_tool.py restart --screen DP-1

# Forcer une cadence d'affichage personnalisée (ex. 30 ou 60 FPS)
./scripts/wallpaper_tool.py restart --fps 30
```

### 7. Gestion du Moteur de Rendu GPU / CPU (`renderer`)
Permet de visualiser le moteur actif ou de basculer instantanément Lucy entre le GPU matériel (Intel UHD 630 @ 30 FPS) et le CPU logiciel (Mesa LLVMpipe @ 20 FPS) avec mise à jour automatique de la configuration persistante :
```bash
# Consulter le mode configuré et les FPS cibles
./scripts/wallpaper_tool.py renderer

# Basculer sur GPU matériel (Intel UHD 630 @ 30 FPS)
./scripts/wallpaper_tool.py renderer gpu

# Basculer sur CPU logiciel (Mesa LLVMpipe @ 20 FPS)
./scripts/wallpaper_tool.py renderer cpu
```

### 8. Audit d'Intégrité des Liens Système (`check-links`)
Parcourt récursivement `dotfiles/` et vérifie que chaque fichier correspond rigoureusement au même numéro d'inode dans `~/.config/`, garantissant qu'aucune écriture n'a rompu les liaisons système (28 hard links) :
```bash
./scripts/wallpaper_tool.py check-links
```
