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
    ├── spotify.py          # Helper MPRIS CLI haute performance (Command Pattern, Facade D-Bus)
    └── spotify-card.py     # Démon GTK3 de carte interactive (Repository, Facade, IPC Service, Observer)
```

---

## 🎨 Spécifications GTK3 & Design System

### 1. Calque de Fond SVG Vectoriel (`bar-bg.svg`)
Le moteur CSS de GTK3 désactive systématiquement `border-radius` dès qu'un `border-image` est employé. Pour obtenir une barre translucide aux arrondis parfaits de 17px avec un dégradé continu de 2px :
- Utilisation de `bar-bg.svg` comme image de fond sur `window#waybar`.
- Le SVG définit un rectangle vectoriel aux coins arrondis `rx="16" ry="16"` avec contour en dégradé SVG natif (`<linearGradient>`).

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

### 3. Hiérarchie Visuelle des Workspaces
- **Actif (`#workspaces button.active`)** : Dégradé plein 45° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`), texte sombre `#090727`, ombre portée cyan (`0 0 10px rgba(0, 240, 255, 0.55)`).
- **Visible (`#workspaces button.visible`)** : Bordure cyan 1.5px, fond teinté cyan translucide, texte cyan `#00f0ff` (identifie l'espace affiché sur l'écran non focus).
- **Inactif (`#workspaces button`)** : Texte bleu-gris discret `#7a8fae`, fond transparent, surbrillance au survol.

---

## 🎵 Architecture du Mini-Lecteur Spotify

### 1. Règle Anti-Capsule Fantôme
Pour éliminer les résidus visuels `[ ]` lorsque Spotify est arrêté :
- **Zéro bordure sur le parent** : `#spotify-player { border: none; background: transparent; padding: 0; margin: 0; }`.
- **Groupe sans espacement** : `"spacing": 0` dans `config.jsonc`.
- **Fusion des contrôles** : `#mpris` assure l'arrondi gauche (`10px 0 0 10px`), `#custom-spotify-next` assure l'arrondi droit (`0 10px 10px 0`), les contrôles intermédiaires suppriment leurs bordures latérales.
- Dès l'arrêt de la lecture, chaque sous-module émet une chaîne vide et Waybar replie automatiquement le conteneur à 0px.

### 2. Daemon Carte Déroulante (`spotify-card.py`)
- **Repository Pattern (`TrackRepository`)** : Persistance atomique des morceaux likés/masqués avec synchronisation SSE Spicetify et verrouillage `threading.Lock`.
- **Facade Pattern (`MPRISPlayerFacade`)** : Appels directs D-Bus pour les commandes de lecture (< 1 ms).
- **Service IPC (`HyprlandIPCService`)** : Repositionnement automatique sous le lecteur Waybar via socket Hyprland.
- **Observer Pattern (`MPRISObserver`)** : Écoute événementielle réactive du signal `org.freedesktop.DBus.Properties.PropertiesChanged`.

---

## 🛠️ Commandes d'Administration

Le script global `hyprbar` permet de piloter la barre et ses démons :

```bash
hyprbar restart   # Redémarrage complet propre de Waybar et de spotify-card
hyprbar reload    # Rechargement à chaud de la configuration CSS (SIGUSR2)
hyprbar toggle    # Masquer / Afficher la barre (SIGUSR1)
hyprbar status    # Afficher les PIDs et l'état des services
```
