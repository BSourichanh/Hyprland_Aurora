# Hyprbar (Waybar & Spotify Suite) (`dotfiles/waybar/`) 🌌

Barre d'état personnalisée pour **Waybar** sous Wayland, combinant esthétique *glassmorphism*, architecture événementielle D-Bus et mini-lecteur Spotify intégré avec carte interactive déroulante.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/waybar/
├── config.jsonc            # Définition de l'agencement, marges et modules Waybar
├── style.css               # Feuilles de style GTK3 (dégradés néon, règles d'arrondis et bulles)
├── bar-bg.svg              # Calque vectoriel de fond (1900x34, rx=16, ry=16, opacité 20%, contour 2px)
└── scripts/
    ├── gpu.py              # Surveillance GPU Intel UHD 630 sans dépendance (Leader-Follower /dev/shm)
    ├── spotify.py          # Helper MPRIS CLI haute performance (Command Pattern, Facade D-Bus)
    └── spotify-card.py     # Démon GTK3 de carte interactive (Repository, Facade, IPC Service, Observer)
```

---

## 🎨 Spécifications GTK3 & Design System

### 1. Calque de Fond SVG Vectoriel (`bar-bg.svg`)
Le moteur CSS de GTK3 désactive systématiquement `border-radius` dès qu'un `border-image` est employé. Pour obtenir une barre translucide aux arrondis parfaits de 17px avec un dégradé continu de 2px :
- Utilisation de `bar-bg.svg` comme image de fond sur `window#waybar`.
- Le SVG définit un rectangle vectoriel aux coins arrondis `rx="16" ry="16"` avec contour en dégradé SVG natif (`<linearGradient>`).
- **Isolation de la translucidité (20%)** : Le tracé vectoriel `stroke` limite strictement le dégradé aux 2px de bordure, empêchant tout saignement de couleur opaque sous le fond verre fumé.

### 2. Modules & Capsules Internes
Les modules internes (`#workspaces`, `#custom-audio`, `#clock`, etc.) exploitent la technique du double arrière-plan :
```css
background-image: 
    linear-gradient(rgba(10, 15, 30, 0.70), rgba(10, 15, 30, 0.70)),
    linear-gradient(45deg, #00f0ff, #7aa2f7, #9778d0);
background-origin: padding-box, border-box;
background-clip: padding-box, border-box;
border: 2px solid transparent;
border-radius: 17px;
```
Cette méthode CSS est privilégiée sur les modules car elle s'adapte dynamiquement et en temps réel aux variations de longueur du texte sans déformer les rayons d'arrondis (contrairement à un SVG étiré en `100% 100%` sous GTK3 qui déforme les angles en ovales étirés).

### 3. Hiérarchie Visuelle des Workspaces
- **Actif (`#workspaces button.active`)** : Dégradé plein 45° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`), texte sombre `#090727`, ombre portée cyan (`0 0 10px rgba(0, 240, 255, 0.55)`).
- **Visible (`#workspaces button.visible`)** : Bordure cyan 1.5px, fond teinté cyan translucide, texte cyan `#00f0ff` (identifie l'espace affiché sur l'écran non focus).
- **Inactif (`#workspaces button`)** : Texte bleu-gris discret `#7a8fae`, fond transparent, surbrillance au survol.

### 4. Triplet Matériel Aurora (CPU > GPU > RAM)
- **Ordre strict des modules de droite** : `cpu` ➔ `custom/gpu` ➔ `memory`.
- **CPU (`cpu`)** : Charge processeur cadencée à 3s, affichée en Bleu Tokyo Night `#7aa2f7` (``).
- **GPU (`custom/gpu` via `gpu.py`)** :
  - Interrogation directe sans dépendance externe des métriques DRM fdinfo du noyau Linux (`/proc/*/fdinfo/*`) et sysfs pour Intel UHD 630 (rendu 3D, décodage vidéo, fréquence MHz, VRAM allouée).
  - **Architecture Leader-Follower (`/dev/shm`)** : Singleton géré par verrou exclusif `fcntl.flock` sur `/dev/shm/waybar_gpu.lock`. La première instance échantillonne les fds kernel et écrit le cache partagé atomiquement ; la seconde instance (écran secondaire) lit directement la mémoire partagée sans scruter `/proc`, divisant par deux le coût CPU.
  - Rendu en Cyan néon `#00f0ff` (`󰢮`).
- **RAM (`memory`)** : Charge mémoire vive en Violet néon `#9778d0` (`󰍅`).

### 5. Compteur de Notifications Dynamique (`custom/notification`)
- Streaming unbuffered via `swaync-client -swb | sed -u 's/"text": "0"/"text": ""/'`.
- Badge numérique en exposant rose néon `{icon}<span foreground='#f43f5e'><sup>{text}</sup></span>` : s'effondre de manière invisible si 0 notification, affiche instantanément le décompte dès réception d'une alerte.

---

## 🎵 Architecture du Mini-Lecteur Spotify

### 1. Masquage au Démarrage & Fusion Vectorielle
- **Zéro bordure sur le parent** : `#spotify-player { border: none; background: transparent; padding: 0; margin: 0; }`. Lorsque Spotify est arrêté ou au démarrage de la session, le groupe s'effondre à 0px sans laisser aucune capsule vide résiduelle `[ ]`.
- **Groupe sans espacement** : `"spacing": 0` dans `config.jsonc` reliant les 5 sous-composants (`mpris`, `custom/spotify-progress`, `prev`, `play-pause`, `next`).
- **Égaliseur audio animé intégré (`custom/spotify-progress`)** : Streaming D-Bus réactif à 4 FPS (`spotify.py --progress`) affichant des barres vectorielles fines (`Noto Sans Mono 9pt`) insérées juste avant le premier timer (` ▃▅   01:23 ━━━ 03:45`), avec largeur constante absolue (28px sans à-coups ni vibration).
- **Continuité chromatique (180deg)** : Dégradé vertical continu (`linear-gradient(180deg, #9778d0 0%, #7aa2f7 50%, #00f0ff 100%)`) garantissant une bordure supérieure violette uniforme et une bordure inférieure cyan pure, sans saut diagonal.
- **Séparateurs verticaux subtils** : Délimitations translucides discrètes (`1px solid rgba(122, 162, 247, 0.25)`) encadrant la progression.
- **Arrondis d'extrémités** : `#mpris` assure l'arrondi gauche (`10px 0 0 10px`) et `#custom-spotify-next` l'arrondi droit (`0 10px 10px 0`). Dès l'arrêt de Spotify, tous les enfants émettent `""` et masquent leurs bordures (`border: none; background: transparent; background-image: none; padding: 0; margin: 0;`).

### 2. Daemon Carte Déroulante (`spotify-card.py`)
- **Repository Pattern (`TrackRepository`)** : Persistance atomique des morceaux likés/masqués avec synchronisation SSE Spicetify et verrouillage `threading.Lock`.
- **Pont Réseau Concurrent** : `ThreadingHTTPServer` non-bloquant pour gérer simultanément le streaming SSE `/events` et les requêtes entrantes `POST /status` et `/songchange`.
- **Facade Pattern (`MPRISPlayerFacade`)** : Appels directs D-Bus pour les commandes de lecture (< 1 ms).
- **Service IPC (`HyprlandIPCService`)** : Repositionnement automatique sous le lecteur Waybar via socket Hyprland avec veille adaptative du curseur (1s au repos).
- **Observer Pattern (`MPRISObserver`)** : Écoute événementielle réactive du signal `org.freedesktop.DBus.Properties.PropertiesChanged`.

---

## 🛠️ Commandes d'Administration

Le script global `hyprbar` permet de piloter la barre et ses démons, tout en garantissant l'éradication des processus orphelins (`swaync-client -swb`, `spotify.py`, `gpu.py`) :

```bash
hyprbar restart   # Redémarrage complet propre de Waybar, spotify-card et purge orphelins
hyprbar reload    # Rechargement à chaud de la configuration CSS (SIGUSR2)
hyprbar toggle    # Masquer / Afficher la barre (SIGUSR1)
hyprbar stop      # Arrêt complet de Waybar et des processus de streaming associés
hyprbar status    # Afficher les PIDs et l'état des services
```
