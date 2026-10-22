# Scripts & CLI d'Administration (`scripts/`) 🛠️

Boîte à outils centralisée pour l'administration du moteur de fond d'écran natif Wayland `aurora-wallpaper`, la génération de masques vectoriels et l'audit d'intégrité de l'environnement Hyprland.

---

## 📁 Contenu du Répertoire

```
scripts/
├── hyprbar              # Gestionnaire CLI Waybar et carte Spotify (anti-fuite de processus)
├── wallpaper_tool.py    # CLI unifié d'administration (moteur natif, masquage, audit, daemon IPC)
└── aurora_mcp_server.py # Micro-serveur MCP FastMCP pour diagnostic Aurora consolidé
```

---

## 🚀 Fonctionnalités du CLI `wallpaper_tool.py`

Le script est exécutable directement depuis la racine du dépôt :

### 1. Surveillance des Processus & Couches Wayland (`status`)
Affiche l'état du processus natif `aurora-wallpaper`, ses métriques CPU (par cœur et global machine), la mémoire RSS et l'empilement des calques Wayland rapporté par Hyprland :
```bash
./scripts/wallpaper_tool.py status
```
*Sortie type :*
```text
=== Aurora Wallpaper Engine (Micro-Moteur Natif Wayland C99) ===
  • Architecture : Single-Pass GLSL + FBO Partagé 1920x1080 (Mutualisé Multi-Écrans)
  • Cadence Cible : 30 FPS fixes
=== Démon Hotplug IPC : Actif [PID 29200] ===
=== État du Processus aurora-wallpaper ===
✓ PID 61591 : CPU: 1.2% (0.2% global) | RAM: 18.2 Mo
  • Fréquence GPU active : 1067 MHz

=== Couches Wayland Détectées (Hyprland) ===
  • DP-1 : Background:swaybg[pid:29198] | Bottom:aurora-wallpaper[pid:61591] | Top:waybar[pid:29304]
  • DP-2 : Background:swaybg[pid:29198] | Bottom:aurora-wallpaper[pid:61591] | Top:waybar[pid:29304]
```

### 2. Régénération du Masque Subpixel (`mask`)
Applique l'algorithme d'ensemencement universel ($D \le 1.8$), la propagation BFS ($D < 18.0$) et la préservation anatomique sur [`ressource/lucy.png`](file:///home/user/Documents/antigravity/hyprland_project/ressource/lucy.png), produisant directement `blackwall_mask.png` pour le shader GLSL unifié :
```bash
./scripts/wallpaper_tool.py mask
```

### 3. Redémarrage Propre du Moteur (`restart`)
Arrête et relance proprement le processus unifié `aurora-wallpaper` sous mutex atomique (`file_mutex` RAII avec `flock` sur `/tmp/wallpaper_restart.lock`) :
```bash
./scripts/wallpaper_tool.py restart
```

### 4. Maintien en Condition Opérationnelle (`ensure`)
Assure que le moteur de rendu tourne et couvre tous les écrans connectés (`DP-1`, `DP-2`). Si absent ou zombie, le relance instantanément sans perturber la session :
```bash
./scripts/wallpaper_tool.py ensure
```

### 5. Démon Hotplug IPC Hyprland (`daemon`)
Démon continu d'arrière-plan écoutant nativement les événements du socket Hyprland (`.socket2.sock`). Détecte instantanément le rallumage ou rebranchement d'un moniteur (`monitoradded`), la déconnexion (`monitorremoved`) ou le rechargement de configuration (`configreloaded`). Applique une temporisation anti-rebond (0.4s) et ré-applique automatiquement `aurora-wallpaper` :
```bash
# Lancer le démon en arrière-plan (géré automatiquement dans hyprland.conf via exec-once)
./scripts/wallpaper_tool.py daemon
```

### 6. Audit d'Intégrité des Liens Système (`check-links`)
Parcourt récursivement `dotfiles/` et vérifie que chaque fichier correspond rigoureusement au même numéro d'inode dans `~/.config/`, garantissant qu'aucune écriture n'a rompu les liaisons système (34 hard links) :
```bash
./scripts/wallpaper_tool.py check-links
```

---

## 🏛️ Architecture & Bonnes Pratiques de Conception

- **Single-Pass GLSL & FBO Partagé** : Rendu exécuté 1 seule fois dans un buffer hors-écran $1920 \times 1080$, puis blitté simultanément sur chaque écran.
- **Gestionnaire de Contexte RAII (`file_mutex`)** : Encapsulation stricte du verrouillage `flock` avec libération déterministe (`try...finally`) prévenant tout blocage ou fichier verrouillé orphelin.
- **Zéro Polling** : Événements IPC socket UNIX Hyprland captés par `select()` non-bloquant.
