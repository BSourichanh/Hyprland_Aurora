# Hyprland Desktop Environment & Dotfiles 🌌

Configuration complète, optimisée et harmonisée pour **Hyprland** sous Linux / Wayland, propulsée par le thème **Aurora** (anciennement inspiré de Hybrid Summer, désormais un design system indépendant et autonome : effet *glassmorphism*, bordures néon en dégradé continu 360° GPU et coins arrondis à 17px).

<p align="center">
  <img src="assets/desktop_preview.png" alt="Aperçu du bureau Hyprland" width="100%" />
</p>

---

## 🎨 Identité Visuelle & Thème (Aurora)

<p align="center">
  <img src="ressource/preview.gif" alt="Fond d'écran animé Lucy" width="70%" />
</p>

Le thème **Aurora** est un environnement visuel et ergonomique sur-mesure, ayant pris son entière indépendance vis-à-vis du socle *Hybrid Summer* d'origine :

- **Palette de couleurs principale** :
  - Cyan électrique lumineux (primaire) : `#00f0ff`
  - Bleu Tokyo Night (secondaire) : `#7aa2f7`
  - Violet néon (accent) : `#9778d0`
  - Fond verre translucide : `rgba(10, 15, 30, 0.20)` (hyprbar) / `rgba(10, 15, 30, 0.65)` à `rgba(10, 15, 30, 0.85)` (cartes, modules et fenêtres)
- **Géométrie & Harmonie** :
  - Rayon d'angle arrondi : **`17px`** obligatoire sur tous les conteneurs (fenêtres Hyprland, Hyprbar, Wofi et la carte Spotify).
  - Épaisseur de bordure : **`2px`** uniforme sur tout l'environnement.
  - Dégradé vectoriel continu à 45° / 135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`) avec rotation continue matérielle GPU 360° sous Hyprland.

---

## 🚀 Fonctionnalités Clés

### 1. Hyprbar (Waybar personnalisée)

<p align="center">
  <img src="assets/waybar_preview.png" alt="Waybar translucide avec dégradé continu" width="100%" />
</p>

- **Fond translucide dépoli** : Utilisation d'un calque SVG vectoriel (`bar-bg.svg`) à 20% d'opacité combiné au flou de composition Hyprland, préservant la netteté des arrondis et le dégradé continu de 2px sans saignement opaque.
- **Bulles de modules dégradées** : Espaces de travail, horloge, contrôleur audio, statut réseau et zone de notification partagent le même encadrement néon glassmorphism.
- **Mini-lecteur Spotify unifié & Barre de progression avec égaliseur** :
  - **Fusion modulaire (`spacing: 0`)** : Regroupement continu des 5 sous-composants (`#mpris`, `#custom-spotify-progress`, commandes `prev`, `play-pause`, `next`).
  - **Égaliseur audio animé fin à largeur constante** : Barres vectorielles Unicode fines (`Noto Sans Mono 9pt`) insérées directement avant le timer écoulé (` ▃▅   01:23 ━━━ 03:45`), garantissant une largeur rigoureusement fixe (28px) sans aucun sautillement horizontal lors de l'animation (4 FPS en lecture cyan `#00f0ff`, figé en pause `#7aa2f7`).
  - **Barre de progression dynamique** : Affichage temps réel de la jauge vectorielle textuelle `───●────` et de l'horodatage (`MM:SS / MM:SS`) via streaming D-Bus natif (`spotify.py --progress`).
  - **Harmonisation chromatique 180°** : Dégradé vertical partagé (`linear-gradient(180deg, #9778d0 0%, #7aa2f7 50%, #00f0ff 100%)`) assurant une ligne haute violette et une ligne basse cyan rigoureusement continues, sans discontinuité diagonale.
  - **Repli total 0px (Anti-capsule fantôme)** : Conteneur parent à zéro bordure (`#spotify-player`). À l'arrêt de la lecture ou au démarrage de session, les modules s'effondrent à 0px sans laisser d'artefact visuel résiduel.
- **Helper MPRIS modulaire (`spotify.py`)** :
  - **Command Pattern & Dispatcher** : Séparation stricte des commandes (`--prev`, `--next`, `--play-pause`, `--progress`).
  - **Facade D-Bus** : Requêtes directes avec fail-safe timeouts (80 ms) et streaming d'égaliseur sans surconsommation CPU.

### 2. Carte Déroulante Spotify (`spotify-card.py`)

<p align="center">
  <img src="assets/spotify_card_preview.png" alt="Carte déroulante Spotify" width="45%" />
</p>

- **Affichage au survol ou au clic** : Déroule instantanément une carte glassmorphism sous le mini-lecteur Waybar.
- **Architecture logicielle & Design Patterns** :
  - **Repository Pattern (`TrackRepository`)** : Gestion thread-safe (`threading.Lock`) et persistance atomique (`tempfile` + `os.replace`) des titres likés et masqués, éliminant tout risque de corruption de données.
  - **Facade Pattern (`MPRISPlayerFacade`)** : Appels D-Bus natifs pour `Next()`, `Previous()`, `PlayPause()`. Suppression totale des sous-processus `playerctl` et `xdotool` (< 1 ms de temps de réponse).
  - **Service & Singleton (`HyprlandIPCService`)** : Abstraction de la communication socket UNIX Hyprland pour le repositionnement ultra-rapide.
  - **Command Pattern (`IPCCommandHandler`)** : Routage découplé des ordres reçus sur le socket UNIX (`show`, `hide`, `toggle`, `like`, `masquer`).
  - **Observer Pattern (`MPRISObserver`)** : Écoute événementielle du signal `PropertiesChanged` sans aucune boucle active.
  - **Data Transfer Object (`TrackMetadata`)** : Typage immuable des métadonnées de piste.
- **Contrôles interactifs** :
  - ** Liker** : Ajoute la chanson aux favoris et mémorise l'état avec synchronisation SSE Spicetify.
  - ** Masquer** : Passe immédiatement à la piste suivante et met le morceau sur liste noire.

### 3. Lanceur d'Applications Wofi (`wofi-toggle.sh` & `style.css`)

<p align="center">
  <img src="assets/wofi_preview.png" alt="Lanceur d'applications Wofi" width="50%" />
</p>

- **Détection de clic extérieur événementielle** : Utilisation de `wait -n` au niveau du noyau Linux (0% de CPU pendant l'ouverture).
- **Style assorti** : Bordure en dégradé continu 135deg avec coins arrondis à 17px et ombre portée cyan néon.

### 4. Écran de Verrouillage Sécurisé (`lock.sh` & `hyprlock.conf`)
- **Pattern RAII / Safe Cleanup Handler** : Restauration déterministe des workspaces et de Waybar encapsulée dans une routine `cleanup()` exécutée sur tous les signaux (`EXIT`, `INT`, `TERM`).
- **Protection multi-écrans** : Déplacement instantané de tous les moniteurs vers des espaces de travail temporaires vides lors du verrouillage pour masquer les applications ouvertes.
- **Requête d'écrans optimisée** : Extraction JSON en passe unique via `jq` sans boucle de sous-processus.

### 5. Menu de Session & Alimentation Épuré (`power-menu.sh` & `power-menu.css`)
- **Modale compacte sans recherche** : Accessible via <kbd>SUPER</kbd> + <kbd>S</kbd>, carte modale centrée de 300x265px sans barre de texte résiduelle.
- **Design en capsules de verre (Glass Cards)** : 5 actions organisées en boutons individuels translucides avec bordures Tokyo Night et surbrillance au survol.
- **Actions directes** : Verrouiller (`lock.sh`), Fermer la session (`hyprctl dispatch exit`), Mettre en veille (`systemctl suspend`), Redémarrer (`systemctl reboot`), Éteindre le PC (`systemctl poweroff`).

### 6. Outil de Capture d'Écran Aurora (`screenshot.sh`)
- **Intégration native sur Impr écran** : Déclenché par la touche <kbd>Print</kbd> ou <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd>.
- **Réticule Aurora thémé** : Outil `slurp` assorti avec bordures cyan 2px (`#00f0ff`) et fond Tokyo Night semi-transparent.
- **Multi-modes** : Sélection rectangulaire, plein écran du moniteur actif (<kbd>SHIFT</kbd> + <kbd>Print</kbd>), fenêtre active (<kbd>SUPER</kbd> + <kbd>Print</kbd>) ou multi-écrans intégral (<kbd>CTRL</kbd> + <kbd>Print</kbd>).
- **Presse-papiers & Notifications** : Copie immédiate dans le presse-papiers Wayland (`wl-copy`) et notification avec vignette miniature.

### 7. Fond d'Écran Animé Lucy & Rendu GPU 60 FPS
- **Rendu Matériel Haute Fluidité** : Animation 60 FPS sur GPU Intel UHD 630 sans écran blanc multi-écrans (`DP-1` et `DP-2`).
- **Sélecteur GPU / CPU** : Basculement instantané via Wofi (<kbd>SUPER</kbd> + <kbd>R</kbd> ➔ "gpu" / "cpu") ou via CLI (`./scripts/wallpaper_tool.py renderer [gpu|cpu]`).
- **Shaders Blackwall Optimisés** : Shader GLSL natif 60 FPS avec fast-path éliminant le calcul sur ~65% des pixels et détourage subpixel sans halo opaque.

---

## 📁 Structure du Projet

```
hyprland_project/
├── dotfiles/
│   ├── hypr/
│   │   ├── hyprland.conf      # Configuration maîtresse d'Hyprland (moniteurs, règles, raccourcis)
│   │   ├── hyprviz.conf       # Paramètres d'apparence complémentaires harmonisés (border_size = 2)
│   │   ├── hypridle.conf      # Gestionnaire d'inactivité (verrouillage auto après 5 min)
│   │   ├── hyprlock.conf      # Écran de verrouillage stylisé avec champ de mot de passe dégradé
│   │   ├── lock.sh            # Script de verrouillage sécurisé avec Safe Cleanup RAII
│   │   ├── wallpaper_renderer.json # Persistance du moteur Lucy actif (GPU/CPU) et des FPS (60/20)
│   │   ├── wallpaper-renderer.desktop # Lanceur d'applications Wofi pour le sélecteur
│   │   ├── scripts/
│   │   │   ├── power-menu.sh  # Menu d'alimentation et session Aurora (SUPER + S)
│   │   │   ├── screenshot.sh  # Capture d'écran (Print Screen, sélection, écran, fenêtre)
│   │   │   ├── wallpaper-select-renderer.sh # Sélecteur graphique Wofi GPU/CPU
│   │   │   ├── reload.sh      # Rechargement unifié Hyprland & Waybar (SUPER + SHIFT + R)
│   │   │   └── wofi-toggle.sh # Lanceur Wofi avec gestion de clic extérieur (wait -n, 0% CPU)
│   │   └── theme-summer/      # Fonds d'écran et ressources graphiques
│   ├── waybar/
│   │   ├── config.jsonc       # Disposition et modules de la barre Waybar
│   │   ├── style.css          # Feuille de style GTK3 avec dégradés néon et bulles unifiées
│   │   ├── bar-bg.svg         # Calque vectoriel de fond (translucidité 0.20 + dégradé continu 2px)
│   │   └── scripts/
│   │       ├── spotify-card.py# Daemon GTK3 (Patterns Repository, Facade, Command, Observer)
│   │       └── spotify.py     # Helper MPRIS modulaire (Command Pattern, Facade D-Bus)
│   ├── wofi/
│   │   ├── config             # Dimensions, disposition et filtrage de Wofi
│   │   ├── style.css          # Style Wofi général avec bordure dégradée 17px
│   │   └── power-menu.css     # Style dédié compact pour la modale d'alimentation (SUPER + S)
│   └── kitty/
│       └── kitty.conf         # Configuration du terminal Kitty (transparence 0.85, Tokyo Night)
├── ressource/                 # Modèle, shaders Blackwall et textures Wallpaper Engine (Lucy)
├── scripts/                   # Outils CLI (wallpaper_tool.py : pack/unpack, mask, sync, audit, renderer)
├── GEMINI.md                  # Directives d'architecture et consignes de développement
└── README.md                  # Documentation générale du projet
```

### 📖 Documentations Détaillées par Composant

Chaque sous-système dispose de sa propre documentation technique dédiée :

| Composant | Description | Documentation |
| :--- | :--- | :--- |
| **Hyprland** | Compositeur Wayland, règles d'affichage, raccourcis, protocole `lock.sh` | [`dotfiles/hypr/README.md`](dotfiles/hypr/README.md) |
| **Waybar & Spotify** | Barre d'état glassmorphism, calque SVG, helper MPRIS et démon carte GTK3 | [`dotfiles/waybar/README.md`](dotfiles/waybar/README.md) |
| **Wofi** | Lanceur d'applications, style CSS 17px et fermeture événementielle sans CPU | [`dotfiles/wofi/README.md`](dotfiles/wofi/README.md) |
| **Kitty** | Émulateur de terminal, translucidité 0.85 et palette Tokyo Night | [`dotfiles/kitty/README.md`](dotfiles/kitty/README.md) |
| **Lucy Theme & Shaders** | Modèle, textures TEXV0005, masque subpixel et shaders Blackwall GPU | [`ressource/README.md`](ressource/README.md) |
| **Scripts & CLI** | Outil d'administration `wallpaper_tool.py`, packaging, sync et audit | [`scripts/README.md`](scripts/README.md) |

---

## 🔗 Gestion des Liens Système

Les fichiers de configuration réels de votre compte utilisateur dans `~/.config/` sont liés directement aux fichiers de ce dépôt :

| Emplacement Système | Cible dans le Dépôt |
| :--- | :--- |
| `~/.config/hypr/` | `dotfiles/hypr/` |
| `~/.config/waybar/` | `dotfiles/waybar/` |
| `~/.config/wofi/` | `dotfiles/wofi/` |
| `~/.config/kitty/` | `dotfiles/kitty/` |

> 💡 **Note :** Toute modification effectuée dans ce dépôt est automatiquement et immédiatement active sur le système.

---

## ⌨️ Raccourcis Clavier Principaux

| Raccourci | Action |
| :--- | :--- |
| <kbd>SUPER</kbd> + <kbd>Return</kbd> / <kbd>SUPER</kbd> + <kbd>Q</kbd> | Ouvrir le terminal Kitty |
| <kbd>SUPER</kbd> + <kbd>R</kbd> | Ouvrir / Fermer le lanceur d'applications (Wofi) |
| <kbd>SUPER</kbd> + <kbd>S</kbd> | Menu de session & alimentation Aurora (Verrouiller, Veille, Éteindre, ...) |
| <kbd>Impr écran</kbd> / <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd> | Capture d'écran interactive (sélection rectangulaire Aurora) |
| <kbd>SHIFT</kbd> + <kbd>Impr écran</kbd> | Capture plein écran du moniteur actif sous le curseur |
| <kbd>SUPER</kbd> + <kbd>Impr écran</kbd> | Capture de la fenêtre active sous focus |
| <kbd>CTRL</kbd> + <kbd>Impr écran</kbd> | Capture intégrale (tous les écrans réunis) |
| <kbd>SUPER</kbd> + <kbd>E</kbd> | Ouvrir le gestionnaire de fichiers (Nautilus) |
| <kbd>SUPER</kbd> + <kbd>C</kbd> | Fermer la fenêtre active |
| <kbd>SUPER</kbd> + <kbd>V</kbd> | Basculer la fenêtre en mode flottant |
| <kbd>SUPER</kbd> + <kbd>L</kbd> | Verrouiller l'écran (`lock.sh` ➔ `hyprlock`) |
| <kbd>SUPER</kbd> + <kbd>TAB</kbd> | Vue d'ensemble des bureaux (Hyprspace Mission Control) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>R</kbd> | Recharger Hyprland & redémarrer la barre (`hyprbar restart`) |
| <kbd>SUPER</kbd> + <kbd>&</kbd> à <kbd>à</kbd> (1-10) | Changer d'espace de travail (AZERTY) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>&</kbd> à <kbd>à</kbd> | Déplacer la fenêtre active vers un espace de travail |

### Contrôles Audio & Multimédia
- **Molette volume / Touches multimédia** : Contrôle natif du volume et lecture/pause (`wpctl`, `playerctl`).
- **Survol de la barre Spotify** : Déroulement automatique de la carte Spotify.
- **Molette sur la barre de progression Spotify** : Avancer / Reculer de 5 secondes dans le morceau.

---

## 🛠️ Utilitaire CLI `hyprbar`

Un utilitaire global est disponible dans le terminal pour administrer la barre et les démons associés :

```bash
hyprbar restart  # Redémarre proprement Waybar et le daemon spotify-card
hyprbar reload   # Rechargement à chaud de la configuration CSS
hyprbar toggle   # Masquer / Afficher la barre
hyprbar stop     # Arrêter la barre et la carte Spotify
hyprbar status   # Vérifier l'état et les PIDs actifs
```

---

## 🛠️ Utilitaire CLI `scripts/wallpaper_tool.py`

CLI dédié à la maintenance du fond d'écran dynamique Lucy (Cyberpunk), aux shaders Blackwall et à l'intégrité du dépôt :

```bash
./scripts/wallpaper_tool.py status         # Affiche l'état des processus DP-1 / DP-2 et FPS actifs
./scripts/wallpaper_tool.py renderer       # Affiche le mode de rendu configuré (GPU / CPU)
./scripts/wallpaper_tool.py renderer gpu   # Bascule Lucy sur le GPU matériel (Intel UHD 630 @ 60 FPS)
./scripts/wallpaper_tool.py renderer cpu   # Bascule Lucy sur le CPU logiciel (Mesa LLVMpipe @ 20 FPS)
./scripts/wallpaper_tool.py mask           # Régénère le masque de détourage subpixel & compile le .tex
./scripts/wallpaper_tool.py sync           # Déploie shaders et assets vers le dossier Steam Workshop
./scripts/wallpaper_tool.py restart        # Redémarre proprement les instances par écran (défaut 60 FPS)
./scripts/wallpaper_tool.py restart --fps 30 # Forcer une cadence spécifique
./scripts/wallpaper_tool.py check-links    # Valide les hard links dotfiles/ <-> ~/.config/
```

---

## 📦 Dépendances Requises

Pour faire fonctionner l'ensemble de ces fonctionnalités :

- **Composants système** : `hyprland`, `waybar`, `wofi`, `kitty`, `hyprlock`, `hypridle`, `swaybg`.
- **Utilitaires Wayland** : `slurp`, `grim`, `wl-clipboard` (`wl-copy`), `playerctl`, `pavucontrol`, `jq`, `wireplumber` (`wpctl`).
- **Python & Bibliothèques** : `python3`, `python3-gi`, `python3-dbus`, `python3-pil` (Pillow).
- **Polices recommandées** : `Noto Sans`, `FontAwesome` (pour les icônes de la barre et du popup).
