# Hyprland Desktop Environment & Dotfiles 🌌

Configuration complète, optimisée et harmonisée pour **Hyprland** sous Linux / Wayland, basée sur le thème **Hybrid Summer** (effet *glassmorphism*, bordures néon en dégradé continu et coins arrondis à 17px).

<p align="center">
  <img src="assets/desktop_preview.png" alt="Aperçu du bureau Hyprland" width="100%" />
</p>

---

## 🎨 Identité Visuelle & Thème

<p align="center">
  <img src="ressource/preview.gif" alt="Fond d'écran animé Lucy" width="70%" />
</p>

- **Palette de couleurs principale** :
  - Cyan électrique lumineux : `#00f0ff`
  - Bleu Tokyo Night : `#7aa2f7`
  - Violet néon : `#9778d0`
  - Fond verre translucide : `rgba(10, 15, 30, 0.20)` (hyprbar) / `rgba(10, 15, 30, 0.85)` (cartes et fenêtres)
- **Géométrie** :
  - Rayon d'angle arrondi : **`17px`** (aligné sur les fenêtres Hyprland, Hyprbar, Wofi et la carte Spotify).
  - Épaisseur de bordure : **`2px`** sur tout l'environnement.
  - Dégradé vectoriel continu à 45° / 135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`).

---

## 🚀 Fonctionnalités Clés

### 1. Hyprbar (Waybar personnalisée)

<p align="center">
  <img src="assets/waybar_preview.png" alt="Waybar translucide avec dégradé continu" width="100%" />
</p>

- **Fond translucide dépoli** : Utilisation d'un calque SVG vectoriel (`bar-bg.svg`) à 20% d'opacité combiné au flou de composition Hyprland, préservant la netteté des arrondis et le dégradé continu de 2px.
- **Bulles de modules dégradées** : Espaces de travail, lecteur Spotify unifié, horloge, contrôleur audio, statut réseau et zone de notification partagent le même encadrement néon glassmorphism.
- **Helper MPRIS modulaire (`spotify.py`)** :
  - **Command Pattern & Dispatcher** : Séparation stricte des commandes (`--prev`, `--next`, `--play-pause`, `--progress`).
  - **Facade D-Bus** : Requêtes directes avec fail-safe timeouts (80 ms) pour garantir la fluidité absolue de la barre.

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
│   │   ├── scripts/
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
│   │   └── style.css          # Style Wofi avec bordure dégradée 17px
│   └── kitty/
│       └── kitty.conf         # Configuration du terminal Kitty (transparence 0.85, Tokyo Night)
├── ressource/                 # Modèle, textures et assets graphiques Wallpaper Engine
├── GEMINI.md                  # Directives d'architecture et consignes de développement
└── README.md                  # Documentation générale du projet
```

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

## 📦 Dépendances Requises

Pour faire fonctionner l'ensemble de ces fonctionnalités :

- **Composants système** : `hyprland`, `waybar`, `wofi`, `kitty`, `hyprlock`, `hypridle`, `swaybg`.
- **Utilitaires Wayland** : `slurp`, `grim`, `playerctl`, `pavucontrol`, `jq`, `wireplumber` (`wpctl`).
- **Python & Bibliothèques** : `python3`, `python3-gi`, `python3-dbus`, `python3-pil` (Pillow).
- **Polices recommandées** : `Noto Sans`, `FontAwesome` (pour les icônes de la barre et du popup).
