# Directives de Développement — Hyprland / Aurora Theme

Document technique de référence pour l'environnement Hyprland (Waybar, Wofi, Spotify Card, Kitty, Lucy Wallpaper Engine).

---

## ⚡ Directives d'Exécution & Concision

- **Style** : Réponses directes, denses, puces courtes, français technique, zéro verbiage.
- **Refactoring & Modifications de Code** :
  - **Toujours proposer** le plan de refactorisation / optimisation et **attendre la confirmation explicite** de l'utilisateur avant d'éditer ou d'appliquer des changements dans les fichiers.
  - Ne jamais modifier le code unilatéralement lors d'une demande de refactoring sans validation préalable.
- **Architecture & Design Patterns** :
  - **Toujours appliquer** les design patterns reconnus et adaptés (ex. Strategy, Factory, Observer, RAII, Object Pooling, séparation des responsabilités) lors de toute conception et refactorisation de code.
- **Git & Gestion de Versions** :
  - **Ne jamais effectuer de `git commit` ni `git push` automatiquement**.
  - Tout commit ou push nécessite impérativement une demande ou validation explicite préalable de l'utilisateur.

---

## 🎨 Charte Graphique Aurora (Constantes Strictes)

### 1. Couleurs & Opacités
| Composant | Valeur / Hex | Rôle |
| :--- | :--- | :--- |
| **Cyan Primaire** | `#00f0ff` / `rgba(0, 240, 255, 1.0)` | Accents principaux, texte actif, lueur |
| **Bleu Secondaire** | `#7aa2f7` | Nuances Tokyo Night, dégradés médians |
| **Violet Accent** | `#9778d0` | Pointes de dégradés, accents néon |
| **Rose / Rouge** | `#f43f5e` / `#f87171` | Alertes, bouton like Spotify, Blackwall |
| **Fond Hyprbar** | `rgba(10, 15, 30, 0.20)` | Barre supérieure (verre fumé ultra-léger) |
| **Fonds Modules** | `rgba(10, 15, 30, 0.65)` à `0.85` | Modules internes, cartes, popups, Wofi |

### 2. Géométrie & Bordures
- **Rayon d'angle (Rounding)** : **`17px`** obligatoire sur tous les conteneurs (fenêtres, Hyprbar, Wofi, popups, Hyprlock).
- **Bordures** : **`2px`** (`border_size = 2`), dégradé vectoriel continu 45°/135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`). Boucle 360° continue sur fenêtres (`animation = borderangle, 1, 50, linear, loop`).

### 3. Règles Critiques GTK3 CSS (Waybar / Wofi)
- ⚠️ **Zéro `border-image`** : Désactive le `border-radius` sous GTK3 (angles coupés à 90°).
- ⚠️ **Zéro `box-shadow` sur `window#waybar`** : Injecte des pixels parasites floutés par Hyprland (`layerrule = blur, waybar`), produisant des coins carrés grisâtres. Conserver `box-shadow: none;`.
- **Modules internes & fenêtres transparentes** : `background: rgba(10, 15, 30, 0.50)` et bordure `rgba(0, 240, 255, 0.6)`. Proscrire le double `background-image` avec dégradé opaque sous-jacent (annule la transparence et rend les conteneurs opaques).
- **Barre externe (`window#waybar`)** : Utiliser le calque vectoriel [`bar-bg.svg`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/waybar/bar-bg.svg) (`stroke="url(#grad)" stroke-width="2"`, $1900 \times 34$, `rx="16"`). Pas de dégradé direct CSS (saignement opaque).

---

## 🖥️ Workspaces & Multi-Écrans

1. **Séparation Stricte** : `all-outputs: false` dans `hyprland/workspaces`. Pas de workspaces persistants forcés (masquage dynamique des espaces vides).
2. **États Visuels des Boutons** :
   - `button.active` : Plein dégradé néon 45° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`), texte sombre `#090727`, ombre `0 0 10px rgba(0, 240, 255, 0.55)`.
   - `button.visible` : Bordure 1.5px `rgba(0, 240, 255, 0.65)`, fond `rgba(0, 240, 255, 0.15)`, texte `#00f0ff` (espace visible sur écran secondaire non focus).
   - `button` (inactif) : Texte discret `#7a8fae`, fond transparent, surbrillance `#00f0ff` au survol.
3. **Hyprspace (`Hyprspace.so`)** : Patch natif multimoniteur ([`hyprspace-multimonitor.patch`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/plugins/hyprspace-multimonitor.patch)) filtrant strictement les workspaces par `ownerID` (pas de fuite entre `DP-1` et `DP-2`).
4. **Auto-Compactage Déterministe (`workspace-autocompact.py`)** : Filtrage strict des règles de verrouillage (`ws_id < 90`) assurant des bornes disjointes nettes (DP-2: 1–5, DP-1: 6–10) sans interférence avec les espaces de masquage 98/99.

---

## 🚀 Lanceur Wofi & Navigation Ergonomique (Souris + Clavier)

1. **Comportement Hybride & Single-Click** :
   - Wofi natif est strictement piloté au clavier. Le patch natif [`wofi-hover-select.patch`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/wofi/wofi-hover-select.patch) ajoute la sélection active au survol de la souris (`#entry:selected`) tout en maintenant le focus continu sur `#input`.
   - Option `single_click=true` requise dans `dotfiles/wofi/config` pour exécution au premier clic gauche.
2. **Règle Critique GTK3 Coordonnées & Signaux** :
   - ⚠️ **Écoute exclusive sur `inner_box`** : Connecter `motion-notify-event` et `enter-notify-event` **uniquement** sur `inner_box` (`GtkFlowBox`).
   - ⚠️ **Zéro écoute sur `window`, `scroll` ou `wrapper_box`** : `inner_box` possédant sa propre `GdkWindow`, `event->x/y` sont déjà dans son repère local. Re-transférer l'événement depuis `window` via `gtk_widget_translate_coordinates` soustrait deux fois la hauteur du champ `#input` (~82px en mode `drun`), décalant la sélection active de 2 entrées vers le haut.
3. **Chaîne de Déploiement du Binaire** :
   - Source locale : `/tmp/wofi_src/` compilée via `ninja -C /tmp/wofi_src/build`.
   - Binaires installés : synchronisation conjointe sur `~/.local/bin/wofi` et `/usr/local/bin/wofi`.
   - Versionnage : régénération systématique du diff unifié dans `dotfiles/wofi/wofi-hover-select.patch`.

---

## 🔔 Centre de Notifications SwayNC & Ergonomie Souris

1. **Menu Contextuel Clic Droit & Blacklist Dynamique** :
   - SwayNC natif ferme la notification sur clic droit sans alternative. Le patch natif [`swaync-blacklist.patch`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/swaync/swaync-blacklist.patch) intercepte `button_press_event` (bouton 3 / clic droit) pour afficher une modale Popover GTK Aurora au curseur (`swaync-context-popover`).
   - Deux actions rapides :
     - « 🚫 Blacklister [App] » : neutralise l'application ciblée sans redémarrage.
     - « ✕ Fermer » : dismiss de la notification.
   - Suspension immédiate du timeout de la notification dès l'ouverture du menu pour éviter sa disparition en cours de lecture.
2. **Script Helper In-Place (`blacklist-app.py`)** :
   - Déclenché de façon asynchrone par SwayNC via `Process.spawn_async`.
   - Injection atomique in-place dans `~/.config/swaync/config.json` sous `notification-visibility` (`state: "ignored"`).
   - ⚠️ **Préservation absolue des hardlinks** : écriture en flux direct sans unlink pour conserver les inodes partagés avec `dotfiles/swaync/`.
   - Rechargement instantané via `swaync-client -R` et toast de confirmation via `notify-send`.
3. **Chaîne de Déploiement du Binaire** :
   - Source locale : `/tmp/swaync_src/` compilée via `ninja -C /tmp/swaync_src/build`.
   - Binaires installés : synchronisation conjointe sur `~/.local/bin/swaync`, `/usr/local/bin/swaync` et `/usr/bin/swaync` (service systemd).
   - Versionnage : régénération systématique du diff unifié dans `dotfiles/swaync/swaync-blacklist.patch`.

---

## 🎵 Mini-Player Spotify (Waybar)

1. **Règle Anti-Capsule Fantôme** :
   ```css
   #spotify-player { border: none; background: transparent; padding: 0; margin: 0; }
   ```
   Waybar ne masquant pas les `GtkBox`, tout padding/bordure sur le conteneur laisserait une capsule vide `[ ]` à l'arrêt de Spotify.
2. **Assemblage Harmonisé** :
   - Groupe `group/spotify-player` (`spacing: 0`) : `mpris`, `custom/spotify-progress`, `custom/spotify-prev`, `custom/spotify-play-pause`, `custom/spotify-next`.
   - Dégradé vertical unifié `linear-gradient(180deg, #9778d0 0%, #7aa2f7 50%, #00f0ff 100%)` sur les enfants pour éliminer les sauts de couleur aux jonctions.
   - Effondrement total à l'arrêt : chaque enfant émet `""` / `border: none; background: transparent; background-image: none; padding: 0; margin: 0;`.
3. **Progression & Égaliseur (`custom/spotify-progress`)** :
   - Streaming 4 FPS (250 ms) via `spotify.py --progress`.
   - Égaliseur Unicode mono 9pt à largeur strictement invariante (**28px** sur les 8 frames) : zéro sautillement horizontal. Format : `[ 01:23 ━━━ 03:45 ]`.
4. **Démon Carte Spotify (`spotify-card.py`)** :
   - Pont SSE multi-clients non-bloquant via `ThreadingHTTPServer` (concurrence `/events` et `POST /status`).
   - Veille adaptative du curseur : réduction du polling à 1s au repos dès l'arrêt de Spotify.
5. **Architecture Événementielle Zéro Polling (`signal: 11`)** :
   - Élimination stricte des forks répétitifs de sous-processus Python (`custom/spotify-prev`, `custom/spotify-play-pause`, `custom/spotify-next`).
   - Configuration de `signal: 11` avec `interval: 30` (filet de sécurité passif) dans `config.jsonc`.
   - Émission réactive de `pkill -RTMIN+11 waybar` :
     - Lors des transitions d'état (`last_state != cls`) dans le flux streaming `spotify.py --progress`.
     - Sur réception du signal D-Bus `PlaybackStatus` dans l'observateur de `spotify-card.py`.
     - Directement dans les handlers `on-click` pour un rafraîchissement visuel instantané.

6. **Triplet Matériel Aurora (`cpu`, `custom/gpu`, `memory`)** :
   - `cpu` : charge processeur en Bleu `#7aa2f7` (``).
   - `custom/gpu` : streaming 2s via `gpu.py` interrogeant les métriques kernel DRM fdinfo (`/proc/*/fdinfo/*` i915) pour Intel UHD 630 sans dépendance externe. Icône `󰢮` en Cyan `#00f0ff`.
   - `memory` : pourcentage RAM en Violet `#9778d0` (`󰍅`).

7. **Compteur de Notifications Dynamique (`custom/notification`)** :
   - Streaming filtré unbuffered `swaync-client -swb | sed -u 's/"text": "0"/"text": ""/'`.
   - Rendu en exposant rose néon `<sup>{text}</sup>` (`#f43f5e`) : masquage transparent si 0 notification, affichage numérique instantané dès réception.

---

## 🔒 Protocole de Verrouillage (`lock.sh` / `hyprlock.conf`)

1. **Masquage Dynamique & Hotplug** :
   - Démon d'écoute IPC d'arrière-plan sur `.socket2.sock` pendant tout le verrouillage.
   - Bascule immédiate vers les espaces réservés vides (`98` sur DP-2, `99` sur DP-1, `persistent:false`).
   - Drapeau atomique `/tmp/hypr_locked` neutralisant `workspace-autocompact.py` (empêche tout démasquage intempestif de fenêtres).
   - À chaque événement `monitoradded` (rallumage d'écran) : ré-application instantanée de l'espace vide et démarrage sélectif du fond d'écran sans toucher l'autre écran.
2. **Isolation Totale de Waybar** :
   - Arrêt complet (`killall waybar` et nettoyage des sous-processus Spotify) pendant le verrouillage. Élimine l'instanciation de barres parasites `visible = true` générées par GTK3 lors de la reconnexion d'écrans.
   - Relance synchronisée via `hyprctl dispatch exec waybar` au déverrouillage.
3. **Restauration d'État Dynamique (RAII)** :
   - Routine `cleanup()` enregistrée sur `trap ... EXIT INT TERM`.
   - Restauration des workspaces initiaux **uniquement sur les moniteurs physiquement connectés** lors du déverrouillage (évite d'écraser la disposition si un écran reste éteint).
4. **Masquage & Suspension des Notifications (SwayNC)** :
   - Fermeture immédiate du panneau de notification (`swaync-client -cp`).
   - Activation atomique du mode Ne pas déranger (`swaync-client -dn`) éliminant toute fuite de toasts sur l'écran verrouillé.
   - Restauration déterministe de l'état DND initial (`swaync-client -df`) dans `cleanup()`.
5. **Horloge Hyprlock & Résilience DPMS (`hyprlock.conf`)** :
   - ⚠️ **Proscrire strictement `$TIME`** : Sujet à une condition de course (*race condition*) dans le thread interne `ResourceGatherer` lors des coupures/sorties de veille DPMS, provoquant un arrêt total des rafraîchissements de l'heure.
   - **Règle absolue** : Utiliser impérativement un timer système explicite asservi au noyau Linux : `text = cmd[update:1000] date +"%H:%M"` (ou `+"%H:%M:%S"`).
6. **Résilience Multi-Processus & Patch Anti-Deadlock (`hyprlock-pam-deadlock.patch`)** :
   - Correctif natif amont (PR #1059) neutralisant le blocage du thread PAM (`std::thread::join()`) à la sortie de session (`isFadingOutOrTerminating` vérifiant `m_bTerminate`).
   - Sonde de détection auto-cicatrisante dans `lock.sh` : purge instantanée de tout processus `hyprlock` fantôme sans surface Wayland active (`hyprctl layers | grep "namespace: hyprlock"`).

---

## 📸 Capture d'Écran & Intégration Terminal

1. **Gel d'Écran Déterministe (`screenshot.sh`)** :
   - Fige instantanément tous les écrans via `hyprpicker -r -z &` dès l'ouverture du mode interactif (Lucy, vidéos et animations arrêtées net).
   - Restauration garantie de l'affichage via `trap 'kill $PICKER_PID' EXIT INT TERM` même lors d'une annulation par <kbd>Échap</kbd> ou clic droit.
2. **Règles de Calques Sans Animation (Hyprland 0.56 / Hyprlang)** :
   - ⚠️ **Syntaxe par bloc déclaratif obligatoire** : Chaque champ exige une valeur (`no_anim = true`). Proscrire l'ancienne forme compacte `layerrule = noanim, selection` qui lève une erreur de parsing `missing a value`.
   - Neutralise le fondu `fade` de fermeture de `slurp` et élimine toute bordure photographiée sur l'image finale.
3. **Menu Contextuel Nautilus ➔ Kitty** :
   - Déploiement en **instance unique** sous `/usr/share/nautilus-python/extensions/` pour éliminer tout doublon dans le clic droit.
   - Purge stricte du paquet propriétaire `nautilus-extension-gnome-terminal`.

---

## 🖼️ Aurora Wallpaper Engine & Lucy Theme (Natif C99)

> 📖 **Spécification Complète** : Micro-moteur Wayland Layer Shell C99 (`src/aurora_wallpaper/aurora-wallpaper`) remplaçant l'ancien `linux-wallpaperengine`.

1. **Architecture Single-Pass & FBO Mutualisé Multi-Écrans** :
   - 1 seul processus unifié gérant simultanément tous les moniteurs connectés (`DP-1` et `DP-2`).
   - Rendu GLSL unifié exécuté **1 seule fois** dans un Framebuffer Object partagé ($1920 \times 1080$), puis copié (*blit*) instantanément sur chaque écran.
   - Charge GPU divisée par 5 (~33% global sur Intel UHD 630 vs ~172% cumulé précédemment), 18 Mo RAM (zéro dépendance V8/Steam/SDL/PulseAudio).
2. **Démon Hotplug IPC Hyprland** :
   - Démon continu `./scripts/wallpaper_tool.py daemon` écoutant `.socket2.sock` (`monitoradded`, `monitorremoved`, `configreloaded`) avec temporisation anti-rebond (0.4s).
   - Commande `./scripts/wallpaper_tool.py ensure` : valide la présence réelle de la couche Wayland `Bottom` (`hyprctl layers -j`).
   - Mutex atomique `flock` sur `/tmp/wallpaper_restart.lock` et verrou singleton `/tmp/wallpaper_daemon.lock`.
3. **Hiérarchie des Couches Wayland** :
   - `Layer 0 (Background)` : `swaybg` (wallpaper statique de secours instantané ~10 ms).
   - `Layer 1 (Bottom)` : `aurora-wallpaper` (Lucy & Blackwall animés 30 FPS fixes).
   - `Layer 2 (Top)` : `waybar`.
   - `Layer 3 (Overlay)` : Wofi, Hyprlock, Spotify Card.
4. **Shader Unifié (`shader.h`)** :
   - Grille cybernétique Blackwall et nébuleuse rouge animée procéduralement.
   - Flux de données doubles (micro et principal) avec étincelles Cyan `#00f0ff`.
   - Détourage subpixel anti-aliasing via masque Blackwall (`ressource/blackwall/blackwall_mask.png`).
   - Glitch Relic géométrique cadencé sans aberration chromatique et ondulation organique de respiration.
   - Fast-Path GPU court-circuitant ~65% de l'écran sous Lucy.

---

## 🏛️ Architecture & Hard Links (`~/.config/`)

Les fichiers sous `dotfiles/` partagent les mêmes inodes (liens durs) avec `~/.config/` :
- `~/.config/hypr/` ➔ `dotfiles/hypr/`
- `~/.config/waybar/` ➔ `dotfiles/waybar/`
- `~/.config/wofi/` ➔ `dotfiles/wofi/`
- `~/.config/kitty/` ➔ `dotfiles/kitty/`
- `~/.config/swaync/` ➔ `dotfiles/swaync/`

⚠️ **Règle absolue** : Ne jamais briser les hard links lors des écritures.
- Les scripts automatisés écrivant dans la configuration (ex. `blacklist-app.py`) doivent impérativement opérer en flux *in-place* direct (`r+`, `seek(0)`, `truncate()`) sans opération de suppression ni de renommage (`unlink` / `replace`).
- Auditer systématiquement l'intégrité via `./scripts/wallpaper_tool.py check-links` (34 fichiers surveillés).

---

## ⚙️ Principes de Performance, Sécurité & Caching

1. **Authentification Polkit** : `hyprpolkitagent` natif Wayland/Hyprland via unité systemd utilisateur `hyprpolkitagent.service`.
2. **Zéro Polling** : Signaux D-Bus MPRIS (`PropertiesChanged`), socket IPC Hyprland événementiel, `wait -n` pour la synchro processus.
3. **Mémoïsation** : Socket Hyprland mis en cache, adresses fenêtres `0x...` mémorisées (évite `hyprctl clients -j`), pochettes Spotify en RAM.
4. **Processus & Concurrence** : Verrous mutex `/tmp/spotify_card.lock` et `/tmp/wallpaper_restart.lock`, nettoyage systématique des sous-processus par `trap ... EXIT INT TERM`.
5. **Écosystème MCP & Sécurité de Contrôle** :
   - `hypruse` : Serveur MCP Wayland natif (`zwlr_virtual_pointer_v1`) avec garde-fou `HYPRUSE_AUTH_GUARD=1` (blocage Polkit/Sudo).
   - Coupure d'urgence matérielle dans `hyprland.conf` : `bind = $mainMod SHIFT, BackSpace, exec, hypruse stop`.
   - `aurora-mcp` : Micro-serveur MCP local FastMCP pour diagnostic consolidé unifié (1 appel) et pilotage de Lucy, Waybar et Spotify.
6. **Résilience des Surfaces Wayland & Détection Anti-Zombie** :
   - Ne jamais évaluer la présence effective d'une interface graphique ou d'un écran de verrouillage uniquement via `pidof` ou `pgrep`.
   - Corréler systématiquement avec l'arborescence des calques Wayland (`hyprctl layers | grep "namespace: <ns>"`).
   - Tout processus fantôme subsistant sans surface active doit être purgé immédiatement avant toute nouvelle exécution (`killall -9 <proc>`).
7. **Déploiement Tripartite des Binaires Patchés** :
   - Pour les composants système sous patch natif (`wofi`, `swaync`, `hyprlock`), maintenir la synchronisation conjointe sur `~/.local/bin/`, `/usr/local/bin/` et `/usr/bin/` (avec préservation du binaire d'origine sous `<binaire>.orig`).
   - Régénérer et hardlinker systématiquement le fichier `.patch` unifié correspondant dans `dotfiles/<composant>/`.

---

## 🧪 Commandes de Référence Rapide

```bash
# Barre d'état & Spotify
hyprbar restart|reload|toggle|status

# Micro-serveur MCP & Diagnostic Aurora
aurora-mcp status|audit

# Hyprland
hyprctl reload

# Aurora Wallpaper Engine CLI (scripts/wallpaper_tool.py)
./scripts/wallpaper_tool.py status         # État PID, moniteurs, CPU%, RAM, couches
./scripts/wallpaper_tool.py daemon         # Démon d'écoute hotplug IPC (restauration auto)
./scripts/wallpaper_tool.py ensure         # Garantir la présence de aurora-wallpaper
./scripts/wallpaper_tool.py restart        # Relancer aurora-wallpaper proprement
./scripts/wallpaper_tool.py mask           # Recalculer masque Blackwall subpixel
./scripts/wallpaper_tool.py check-links    # Auditer intégrité des 34 hard links

# Validation syntaxique rapide
bash -n dotfiles/hypr/lock.sh dotfiles/hypr/scripts/*.sh
python3 -m py_compile dotfiles/waybar/scripts/*.py scripts/*.py
python3 -c "import json; json.load(open('dotfiles/waybar/config.jsonc'))"
```
