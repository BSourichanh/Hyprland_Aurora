# Aurora — Hyprland Desktop Environment & Dotfiles 🌌

Configuration complète, moderne et haute performance pour **Hyprland** sous Linux / Wayland, propulsée par le thème **Aurora**.

- **Style Visuel** : Esthétique néon *glassmorphism* combinant des surfaces en verre fumé translucide (`rgba(10, 15, 30, 0.50)`), des bordures en dégradé vectoriel continu 45°/135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`) animées par rotation 360° matérielle sous GPU, et une courbure géométrique stricte à `17px` sur tous les conteneurs.
- **Fonctionnement & Architecture** : Écosystème Wayland hautement réactif articulé autour d'une architecture événementielle zéro-polling (signaux D-Bus MPRIS, sockets IPC Hyprland). Il intègre une barre d'état Waybar dynamique avec mini-lecteur Spotify synchrone, un lanceur d'applications Wofi translucide patché souris/clavier, un moteur de fond d'écran animé Wallpaper Engine multimoniteur avec démon IPC de reconnexion à chaud (hotplug), un auto-compactage déterministe des workspaces multi-écrans, un protocole de verrouillage sécurisé avec masquage atomique des surfaces et une passerelle MCP native pour l'automatisation IA.

<p align="center">
  <img src="assets/desktop_preview.png" alt="Aperçu du bureau Hyprland" width="100%" />
</p>

---

## 🎨 Identité Visuelle & Thème (Aurora)

<p align="center">
  <img src="ressource/preview.gif" alt="Fond d'écran animé Lucy" width="70%" />
</p>

Le thème **Aurora** est un environnement visuel et ergonomique sur-mesure :

- **Palette de couleurs principale** :
  - Cyan électrique lumineux (primaire) : `#00f0ff`
  - Bleu Tokyo Night (secondaire) : `#7aa2f7`
  - Violet néon (accent) : `#9778d0`
  - Fond verre translucide : `rgba(10, 15, 30, 0.50)` (hyprbar, cartes, modules, popups et Wofi)
- **Géométrie & Harmonie** :
  - Rayon d'angle arrondi : **`17px`** obligatoire sur tous les conteneurs (fenêtres Hyprland, Hyprbar, Wofi et la carte Spotify).
  - Épaisseur de bordure : **`2px`** uniforme sur tout l'environnement.
  - Dégradé vectoriel continu à 45° / 135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`) avec rotation continue matérielle GPU 360° sous Hyprland.
  - Invariant Ergonomique Utilisateur (`input:follow_mouse = 0`) : Mode Click-to-Focus strict scrupuleusement préservé, garantissant une étanchéité totale du focus lors des déplacements de curseur en multi-écrans (`DP-2` / `DP-1`).

---

## ⚡ Déploiement & Installation Rapide

Un script d'installation automatisé et idempotent est disponible à la racine du dépôt pour déployer l'intégralité de l'environnement en une seule commande :

```bash
# 1. Cloner le dépôt
git clone https://github.com/BSourichanh/Hyprland_Aurora.git
cd Hyprland_Aurora

# 2. Lancer le déploiement complet
./setup.sh
```

### Ce que fait automatiquement `./setup.sh` :
1. **Dépendances système** : Détecte votre gestionnaire de paquets (`apt`, `pacman`) et installe les composants Wayland, polices, polkit et bibliothèques Python requises (saut possible via `./setup.sh --no-deps` ; configuration Nautilus isolée via `./scripts/setup/packages.sh --nautilus-only`).
2. **Sauvegarde préventive** : Archive automatiquement vos configurations existantes dans `~/.config/aurora_backup_<date>/`.
3. **Hard Links stricts** : Établit les **42 hard links physiques nominaux** (mêmes inodes) entre `dotfiles/` et `~/.config/` garantissant la synchronisation bidirectionnelle immédiate.
4. **Permissions & Exécutables** : Règle les permissions `chmod +x` sur tous les scripts et déploie l'utilitaire `hyprbar` et le wrapper `aurora-mcp` dans `~/.local/bin/`.
5. **Masques Blackwall & Caches** : Régénère le masque vectoriel haute fidélité `blackwall_mask.png` et configure le dossier runtime sécurisé `$AURORA_RUNTIME_DIR`.
6. **Audit d'intégrité** : Valide la conformité complète des liaisons via `./scripts/wallpaper_tool.py check-links`.

---

## 🚀 Fonctionnalités Clés

### 1. Hyprbar (Waybar personnalisée)

<p align="center">
  <img src="assets/waybar_preview.png" alt="Waybar translucide avec dégradé continu" width="100%" />
</p>

- **Fond translucide dépoli** : Utilisation d'un calque SVG vectoriel (`bar-bg.svg`) à 50% d'opacité (`rgba(10, 15, 30, 0.50)`) combiné au flou de composition Hyprland, préservant la netteté des arrondis et le dégradé continu de 2px sans saignement opaque.
- **Bulles de modules dégradées** : Espaces de travail, horloge, contrôleur audio, statut réseau et zone de notification partagent le même encadrement néon glassmorphism.
- **Mini-lecteur Spotify unifié & Barre de progression avec égaliseur** :
  - **Fusion modulaire (`spacing: 0`)** : Regroupement continu des 5 sous-composants (`#mpris`, `#custom-spotify-progress`, commandes `prev`, `play-pause`, `next`).
  - **Égaliseur audio animé fin à largeur constante** : Barres vectorielles Unicode fines (`Noto Sans Mono 9pt`) insérées directement avant le timer écoulé (` ▃▅   01:23 ━━━ 03:45`), garantissant une largeur rigoureusement fixe (28px) sans aucun sautillement horizontal lors de l'animation (4 FPS en lecture cyan `#00f0ff`, figé en pause `#7aa2f7`).
  - **Barre de progression dynamique** : Affichage temps réel de la jauge vectorielle textuelle `───●────` et de l'horodatage (`MM:SS / MM:SS`) via streaming D-Bus natif (`spotify.py --progress`).
  - **Harmonisation chromatique 180°** : Dégradé vertical partagé (`linear-gradient(180deg, #9778d0 0%, #7aa2f7 50%, #00f0ff 100%)`) assurant une ligne haute violette et une ligne basse cyan rigoureusement continues, sans discontinuité diagonale.
  - **Repli total 0px (Anti-capsule fantôme)** : Conteneur parent à zéro bordure (`#spotify-player`). À l'arrêt de la lecture ou au démarrage de session, les modules s'effondrent à 0px sans laisser d'artefact visuel résiduel.
- **Triplet Matériel Aurora (CPU > GPU > RAM)** :
  - **CPU (`cpu`)** : Charge processeur en Bleu `#7aa2f7` (``).
  - **GPU (`custom/gpu`)** : Métriques kernel DRM fdinfo (`/proc/*/fdinfo/*` i915) pour Intel UHD 630 sans dépendance externe. Architecture Leader-Follower via `/dev/shm` divisant les lectures système par 2 en configuration multi-écrans. Icône `󰢮` en Cyan `#00f0ff`.
  - **RAM (`memory`)** : Pourcentage de mémoire vive en Violet `#9778d0` (`󰍅`).
- **Compteur de Notifications Dynamique (`custom/notification`)** :
  - Flux continu sans tampon `swaync-client -swb | sed -u 's/"text": "0"/"text": ""/'`.
  - Badge numérique en exposant rose néon `{icon}<span foreground='#f43f5e'><sup>{text}</sup></span>` : masqué si 0 alerte, visible dès la première notification reçue.
- **Architecture Événementielle Zéro-Polling (`signal: 11`)** :
  - Élimination stricte des forks répétitifs de sous-processus Python (`custom/spotify-prev`, `custom/spotify-play-pause`, `custom/spotify-next`).
  - Configuration de `signal: 11` avec `interval: 30` (filet de sécurité passif) dans `config.jsonc`.
  - Rafraîchissement instantané via signal POSIX temps réel `pkill -RTMIN+11 waybar` lors des clics et sur réception du signal D-Bus `PlaybackStatus`.
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

- **Comportement Hybride & Single-Click** :
  - Option `single_click=true` configurée dans `dotfiles/wofi/config` pour un lancement immédiat au premier clic souris.
  - Patch natif GTK3 ([`wofi-hover-select.patch`](dotfiles/wofi/wofi-hover-select.patch)) : synchronise dynamiquement la sélection active (`#entry:selected`) au survol du curseur de la souris sans jamais voler le focus clavier de la barre de recherche (`#input`).
  - Correction géométrique GTK3 : écoute exclusive sur `inner_box` avec coordonnées locales directes, évitant tout décalage d'index lié à la hauteur du champ de recherche.
- **Détection de clic extérieur événementielle** : Utilisation de `wait -n` au niveau du noyau Linux (0% de CPU pendant l'ouverture).
- **Style assorti** : Bordure en dégradé continu 135deg avec coins arrondis à 17px et ombre portée cyan néon.

### 4. Écran de Verrouillage Sécurisé & Politique Veille / DPMS (`lock.sh` & Demande Utilisateur)
- **Politique Énergétique & Veille (Zéro Écran Noir sous Verrou — Demande Utilisateur)** :
  - **Extinction d'écran (DPMS off 330s) et Dimming (150s) inhibés sous verrou** : Les Paliers 1 (`150s`, baisse de luminosité) et 3 (`330s`, `dpms off`) de `hypridle.conf` sont inhibés dès le verrouillage via la garde atomique :
    `[ ! -f "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora/hypr_locked" ] && ! pgrep -x hyprlock >/dev/null`.
  - **Mise en veille PC (`systemctl suspend` à 1800s) bloquée sous verrou** : Palier 4 protégé par la même double garde runtime.
  - **Réveil forcé DPMS et inhibition sleep/idle dans `lock.sh`** : `lock.sh` force immédiatement `hyprctl dispatch dpms on` avant verrouillage et encapsule `hyprlock` sous `systemd-inhibit --what=sleep:idle --who="Aurora Lock" --why="Session verrouillée : veille PC et écran noir désactivés" --mode=block hyprlock 9>&-`.
  - **Écran de veille actif & Cadence 60 FPS (Choix Utilisateur)** : Le fond animé Lucy et l'horloge restent allumés en permanence sans aucun écran noir sous verrou. Par choix explicite de l'utilisateur pour une fluidité visuelle maximale sur `hyprlock`, le framerate de l'écran de verrouillage est maintenu à 60 FPS (16 ms), alors que la session de travail normale est cadencée à 30 FPS (33 ms). En session déverrouillée, la cascade normale (dim 150s, lock 300s, DPMS 330s, suspend 1800s) est active. Section `general {}` configurée avec `inhibit_sleep = 3`.
- **Masquage Dynamique & Protection Hotplug v2** : Démon d'écoute IPC d'arrière-plan sur `.socket2.sock` prenant en charge la spécification Hyprland (`monitoraddedv2` / `monitorremovedv2`). Bascule instantanée vers les espaces vides réservés (`98` sur DP-2, `99` sur DP-1).
- **Isolation Totale de Waybar** : Arrêt complet de Waybar pendant le verrouillage pour éliminer les réapparitions intempestives lors du hotplug d'écrans, et relance propre à la saisie du mot de passe.
- **Confidentialité des Notifications (SwayNC)** : Activation automatique du mode Ne Pas Déranger (`swaync-client -dn`) et fermeture forcée du volet pour supprimer toute bulle de notification sur l'écran de verrouillage. Restauration de l'état DND au déverrouillage.
- **Neutralisation de l'Auto-Compacteur & Runtime Sécurisé** : Drapeau atomique `$AURORA_RUNTIME_DIR/hypr_locked` (`${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora`, mode `0700`) empêchant `workspace-autocompact.py` de déplacer des workspaces pendant le verrouillage.
- **Horloge Anti-Freeze Résiliente DPMS** : Horloge asservie au système (`text = cmd[update:1000] date +"%H:%M"`) garantissant l'heure exacte.
- **Résilience Multi-Processus & Détection Fiable** : Correctif natif amont PAM (PR #1059) anti-deadlock. Détection de verrouillage fiabilisée par `pgrep -x hyprlock`, non-blocking `flock` sur `$AURORA_RUNTIME_DIR/hypr_lock_instance.lock` et présence du drapeau `$AURORA_RUNTIME_DIR/hypr_locked`.
- **Pattern RAII / Restauration Dynamique** : Restauration des workspaces d'origine encapsulée dans une routine `cleanup()` exécutée sur tous les signaux (`EXIT`, `INT`, `TERM`), ciblant uniquement les écrans réellement allumés.

### 5. Menu de Session & Alimentation Épuré (`power-menu.sh` & `power-menu.css`)

<p align="center">
  <img src="assets/power_menu_preview.png" alt="Menu de session Wofi Aurora" width="35%" />
</p>

- **Modale compacte sans recherche** : Accessible via <kbd>SUPER</kbd> + <kbd>S</kbd>, carte modale centrée de 300x265px sans barre de texte résiduelle.
- **Design en capsules de verre (Glass Cards)** : 5 actions organisées en boutons individuels translucides avec bordures Tokyo Night et surbrillance au survol.
- **Actions directes** : Verrouiller (`lock.sh`), Fermer la session (`hyprctl dispatch exit`), Mettre en veille (`systemctl suspend`), Redémarrer (`systemctl reboot`), Éteindre le PC (`systemctl poweroff`).

### 6. Outil de Capture d'Écran Aurora (`screenshot.sh`)
- **Intégration native sur Impr écran** : Déclenché par la touche <kbd>Print</kbd> ou <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd>.
- **Gel Instantané de l'Affichage (Freeze Screen)** : Utilisation de `hyprpicker -r -z` figeant immédiatement l'ensemble des moniteurs dès l'ouverture du mode sélection. Zéro décalage temporel ou animation en mouvement (Lucy, vidéos, Spotify) pendant la sélection rectangulaire.
- **Élimination Définitive des Bordures Résiduelles** : Règles de calque déclaratives Hyprland (`selection_noanim` et `hyprpicker_noanim`) désactivant toute animation de sortie sur les couches de sélection, empêchant `grim` de photographier l'estompement du cadre `slurp`.
- **Réticule Aurora affiné** : Outil `slurp` assorti avec bordures cyan 1px (`#00f0ff`) et fond Tokyo Night semi-transparent.
- **Multi-modes** : Sélection rectangulaire gelée, plein écran du moniteur actif (<kbd>SHIFT</kbd> + <kbd>Print</kbd>), fenêtre active (<kbd>SUPER</kbd> + <kbd>Print</kbd>) ou multi-écrans intégral (<kbd>CTRL</kbd> + <kbd>Print</kbd>).
- **Presse-papiers & Notifications** : Copie immédiate dans le presse-papiers Wayland (`wl-copy`), libération déterministe RAII (`trap`) et notification avec vignette miniature.

### 7. Centre de Notifications & Contrôle Aurora (SwayNC)
- **Thématisation Aurora GTK3** :
  - Rayon de courbure strict à **`17px`** sur les conteneurs de notification et sur le volet de contrôle (`.control-center`).
  - Bordures néon cyan `2px` (`#00f0ff` / `rgba(0, 240, 255, 0.60)`) et arrière-plan glassmorphism fumé `rgba(10, 15, 30, 0.80)`.
  - Flou matériel Hyprland avec règles dédiées (`layerrule = blur, swaync-control-center` et `layerrule = blur, swaync-notification-window`).
- **Widgets Intégrés & Contrôles** :
  - Volet latéral rétractable déclenché par le raccourci <kbd>SUPER</kbd> + <kbd>N</kbd> (`swaync-client -t -sw`).
  - Menu contextuel au clic droit via patch natif Vala ([`swaync-blacklist.patch`](dotfiles/swaync/swaync-blacklist.patch)) ouvrant un Popover GTK Aurora :
    - « 🚫 Blacklister [App] » : injection atomique *in-place* dans `config.json` via [`blacklist-app.py`](dotfiles/swaync/scripts/blacklist-app.py) sans rupture des hardlinks.
    - « ✕ Fermer » : dismiss de la notification avec suspension de l'expiration au survol.
  - Interrupteur Ne Pas Déranger (DND) stylisé avec retour d'état instantané.
  - Widget de contrôle multimédia MPRIS et historique des notifications classées avec boutons d'effacement individuel ou global.
  - Différenciation chromatique des urgences : alertes critiques signalées par des accents rouge néon (`#f43f5e`).
- **Protocole de Confidentialité sous Verrouillage** :
  - Bascule automatique en mode DND (`swaync-client -dn`) et fermeture du volet à l'entrée dans `lock.sh`.
  - Zéro fuite visuelle : aucune bulle de notification n'apparaît sur l'écran verrouillé ; les alertes restent enregistrées en arrière-plan et sont consultables au déverrouillage.

### 8. Fond d'Écran Animé Lucy & Micro-Moteur Natif C99 (`aurora-wallpaper`)
- **Micro-moteur C99 optimisé (`98360 o`) & Single-Pass GLSL** : Rendu exécuté 1 seule fois dans un FBO partagé (`GL_RGB` / `GL_RGBA`) puis copié sur `DP-1` et `DP-2`. Binaire C99 compact (**98360 octets**, -57.3% vs 230 Ko initial), VBO statique et cache de verrouillage 250 ms.
- **Région Opaque Wayland & 0 `swaybg`** : Déclaration de région opaque via `wl_surface_set_opaque_region()`. `swaybg` redondant éliminé (**0 processus résiduel**, layer 0 libéré, suppression intégrale de l'alpha-blending compositeur).
- **Consommation & Cadencement Adaptatif** : 30 FPS fixes (33 ms) en session active (~1.9% CPU, ~59.8 Mo VRAM) et maintien à 60 FPS (16 ms) sous écran de verrouillage (`$AURORA_RUNTIME_DIR/hypr_locked`) par arbitrage explicite de l'utilisateur pour garantir une fluidité d'animation absolue sous `hyprlock`.
- **Démon d'Auto-Guérison Hotplug (`wallpaper_tool.py daemon`)** : Supervision IPC continue (`.socket2.sock`) restaurant automatiquement la surface lors d'un rebranchement d'écran ou du réveil DPMS.
- **Shader Unifié (`shader.h`)** : Fast-path sous Lucy, étincelles cyan, pré-calcul CPU des paramètres temporels (`u_TimeParams`) et suppression des fonctions transcendantes `pow()`.

### 9. Écosystème MCP & Automatisation IA (Model Context Protocol)
- **Micro-serveur FastMCP Aurora (`scripts/aurora_mcp_server.py`)** :
  - Fournit un diagnostic complet et le pilotage consolidé de l'environnement en un appel.
  - **13 Outils réels intégrés** : `get_aurora_status`, `manage_wallpaper`, `manage_hyprbar`, `lock_session`, `reload_all`, `audit_hardlinks`, `wofi_launch`, `compact_workspaces`, `switch_theme`, `manage_swaync`, `manage_blacklist`, `audio_control`, `spotify_control`. (Tout outil renderer obsolète a été exclu du catalogue).
  - Modes CLI : `aurora-mcp serve` (stdio MCP), `aurora-mcp status` (JSON), `aurora-mcp audit` (JSON hardlinks), `aurora-mcp reload` (JSON reload).
- **Contrôle Wayland Sécurisé (`hypruse`)** :
  - Serveur MCP Wayland natif via `zwlr_virtual_pointer_v1`.
  - Garde-fou d'authentification active (`HYPRUSE_AUTH_GUARD=1`) bloquant toute interaction involontaire avec les invites de mot de passe Polkit / Sudo.
  - Coupure d'urgence matérielle sous Hyprland via <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>BackSpace</kbd> (`hypruse stop`).

### 10. Bilan des Optimisations Système (OPT-1 à OPT-9) & Performances Réelles

Les 9 optimisations issues de l'audit sont **implémentées et vérifiées** (suite zéro-régression : **20/20 tests PASS** via `./scripts/verify_aurora.sh --read-only`) :

| ID | Domaine | Description & Implémentation | Métrique & Gain Réel Mesuré |
| :--- | :--- | :--- | :--- |
| **OPT-1** | GPU / Wayland | Région opaque (`wl_surface_set_opaque_region`), FBO `GL_RGB`, arrêt auto `swaybg` | **0 swaybg** (layer 0 libéré), zéro blending sur 2x 1080p |
| **OPT-2** | Binaire C99 | Binaire `aurora-wallpaper` C99 optimisé, VBO statique, cache verrou 250 ms | **98360 octets** (-57.3%), 60 FPS (16 ms) sous verrou (choix utilisateur), -92% syscalls |
| **OPT-3** | Shader GLSL | Uniforme `u_TimeParams` précalculé CPU, `pow()` transcendants éliminés | ~12 ops invariantes/pixel supprimées, 4 multiplications natives |
| **OPT-4** | Compositeur | Flou Kawase natif unique (`plugin:hyprglass` restreint à `hyprlock`), VFR actif | Double flou éliminé sur Waybar/Wofi, `debug:vfr = true` actif |
| **OPT-5** | Watchdog IPC | Sockets UNIX directs (`j/layers`, `j/monitors`) et détection `/proc` sans fork | **0.41 ms** (vs 19.34 ms, **-97.8%**, x47), 0 fork / 10s |
| **OPT-6** | IPC Hover | Caches runtime dir et socket Hyprland dans `hypr_ipc.py` (boucle 20 Hz) | **3.38 ms** / 50 req (vs 7.34 ms, **-54.0%**), 0 syscall redondant |
| **OPT-7** | MCP Workspaces | Exécution *in-process* de `compact_workspaces` et cache `_MONITOR_CONFIGS_CACHE` | **0.33 ms** (vs 33.77 ms bloqué, **-99.0%**), verrou débloqué |
| **OPT-8** | Waybar/Spotify | Boutons en `interval: "once"`, déduplication pause, backoff D-Bus, suppression timer 2s | **-12 forks Python/min**, 0 redraw en pause, 0 timer 2s |
| **OPT-9** | MCP Diagnostic | Scan `/proc` unifié (`comm`, `exe`, `status`), socket direct et parallélisation | **20.08 ms** total (vs 89.52 ms, **-77.6%**) ; socket+proc **8.44 ms** |

---

## 📁 Structure du Projet

```
hyprland_project/
├── dotfiles/
│   ├── hypr/
│   │   ├── hyprland.conf      # Configuration maîtresse d'Hyprland (moniteurs, règles, follow_mouse=0)
│   │   ├── hyprviz.conf       # Paramètres d'apparence complémentaires harmonisés (border_size = 2)
│   │   ├── hypridle.conf      # Démon d'inactivité (DPMS 330s, garde suspend 1800s, inhibit_sleep = 3)
│   │   ├── hyprlock.conf      # Écran de verrouillage stylisé avec champ de mot de passe dégradé
│   │   ├── hyprlock-pam-deadlock.patch # Patch C++ anti-deadlock PAM (PR #1059)
│   │   ├── lock.sh            # Script de verrouillage sécurisé avec Safe Cleanup RAII
│   │   ├── plugins/
│   │   │   ├── Hyprspace.so   # Plugin Mission Control (SUPER + TAB)
│   │   │   └── hyprspace-multimonitor.patch # Patch natif filtrant les workspaces par écran
│   │   ├── scripts/
│   │   │   ├── hypr_ipc.py    # Client/serveur IPC événementiel Hyprland (.socket.sock / .socket2.sock)
│   │   │   ├── hyprlock_state.py # Gestionnaire d'état et masquage d'espaces (98 DP-2 / 99 DP-1)
│   │   │   ├── wallpaper_daemon.sh # Démon de résilience hotplug et réveil DPMS
│   │   │   ├── workspace-autocompact.py # Auto-compactage dynamique des workspaces (DP-2 / DP-1)
│   │   │   ├── power-menu.sh  # Menu d'alimentation et session Aurora (SUPER + S)
│   │   │   ├── screenshot.sh  # Capture d'écran (Print Screen, sélection, écran, fenêtre)
│   │   │   ├── reload.sh      # Rechargement unifié Hyprland & Waybar (SUPER + SHIFT + R)
│   │   │   └── wofi-toggle.sh # Lanceur Wofi avec gestion de clic extérieur (wait -n, 0% CPU)
│   │   └── theme-summer/      # Fonds d'écran et ressources graphiques
│   ├── waybar/
│   │   ├── config.jsonc       # Disposition et modules de la barre Waybar (signal: 11, CPU>GPU>RAM)
│   │   ├── style.css          # Feuille de style GTK3 avec dégradés néon et bulles unifiées
│   │   ├── bar-bg.svg         # Calque vectoriel de fond (translucidité 0.50 + dégradé continu 2px)
│   │   └── scripts/
│   │       ├── gpu.py         # Métriques GPU Intel UHD 630 sans dépendance (Leader-Follower $AURORA_RUNTIME_DIR)
│   │       ├── spotify-card.py# Daemon GTK3 (Patterns Repository, Facade, Command, Observer)
│   │       ├── spotify_hover.py # Déroulement au survol et capture position curseur
│   │       ├── spotify_ipc.py # Client socket IPC vers le démon carte
│   │       ├── spotify_mpris.py # Écoute événementielle D-Bus MPRIS
│   │       ├── spotify.py     # Helper MPRIS modulaire (Command Pattern, Facade D-Bus)
│   │       └── spotify_server.py # Serveur HTTP SSE pour diffusion des événements
│   ├── wofi/
│   │   ├── config             # Dimensions, disposition et filtrage de Wofi (single_click=true)
│   │   ├── style.css          # Style Wofi général avec bordure dégradée 17px
│   │   ├── power-menu.css     # Style dédié compact pour la modale d'alimentation (SUPER + S)
│   │   └── wofi-hover-select.patch # Patch GTK3 de sélection fluide au survol de souris
│   ├── swaync/
│   │   ├── config.json        # Structure des widgets (DND, MPRIS, liste) et dimensions (420px)
│   │   ├── style.css          # Feuille de style GTK3 (glassmorphism 0.80, coins 17px, bordures cyan 2px)
│   │   ├── swaync-blacklist.patch # Patch natif Vala pour menu contextuel clic droit
│   │   ├── scripts/
│   │   │   └── blacklist-app.py # Insertion in-place dans notification-visibility (respect hardlinks)
│   │   └── README.md          # Documentation technique dédiée au centre de notifications
│   └── kitty/
│       └── kitty.conf         # Configuration du terminal Kitty (transparence 0.50, Tokyo Night)
├── assets/                    # Captures d'écran et aperçus visuels du thème
├── ressource/                 # Modèle, textures et masques subpixel Blackwall (Lucy)
│   └── nautilus/              # Extension Nautilus python pour ouverture directe Kitty
├── src/
│   └── aurora_wallpaper/      # Micro-moteur Wayland C99 natif (Single-Pass GLSL + FBO 30 FPS session / 60 FPS lock)
├── scripts/
│   ├── hyprbar                # Gestionnaire CLI Waybar et carte Spotify (anti-fuite de processus)
│   ├── wallpaper_tool.py      # Outils CLI (moteur natif, mask, audit 42 hardlinks, daemon, ensure)
│   ├── wallpaper_daemon.py    # Démon d'écoute IPC Hyprland (.socket2.sock)
│   ├── theme_switcher.py      # Sélecteur de thèmes dynamique (apply, list, status)
│   ├── aurora_runtime.py      # Contrat runtime sécurisé $AURORA_RUNTIME_DIR (0700)
│   ├── verify_aurora.sh       # Harnais de test unifié zéro-régression (supporte --read-only)
│   └── aurora_mcp_server.py   # Serveur MCP local FastMCP (13 outils réels)
├── hooks/
│   └── pre-commit             # Hook Git garantissant les 42 hardlinks et la volumétrie < 500L
├── setup.sh                   # Script d'installation modulaire et validation des 42 hardlinks
└── README.md                  # Documentation générale du projet
```

### 📖 Documentations Détaillées par Composant

Chaque sous-système dispose de sa propre documentation technique dédiée :

| Composant | Description | Documentation |
| :--- | :--- | :--- |
| **Hyprland** | Compositeur Wayland, règles d'affichage, raccourcis, protocole `lock.sh` | [`dotfiles/hypr/README.md`](dotfiles/hypr/README.md) |
| **Waybar & Spotify** | Barre d'état glassmorphism, architecture événementielle `signal: 11` et carte GTK3 | [`dotfiles/waybar/README.md`](dotfiles/waybar/README.md) |
| **Wofi** | Lanceur d'applications, patch souris single-click/hover et style CSS 17px | [`dotfiles/wofi/README.md`](dotfiles/wofi/README.md) |
| **SwayNC** | Centre de notifications, thème Aurora glassmorphism 17px et mode DND | [`dotfiles/swaync/README.md`](dotfiles/swaync/README.md) |
| **Kitty** | Émulateur de terminal, translucidité 0.50 et palette Tokyo Night | [`dotfiles/kitty/README.md`](dotfiles/kitty/README.md) |
| **Lucy Theme & Shaders** | Modèle, textures TEXV0005, masque subpixel et shaders Blackwall GPU | [`ressource/README.md`](ressource/README.md) |
| **Scripts & MCP** | Administration CLI `wallpaper_tool.py` et micro-serveur `aurora-mcp` | [`scripts/README.md`](scripts/README.md) |

---

## 🔗 Gestion des Liens Système

Les fichiers de configuration réels de votre compte utilisateur dans `~/.config/` sont liés directement aux fichiers de ce dépôt (**42 hard links physiques nominaux**) :

| Emplacement Système | Cible dans le Dépôt |
| :--- | :--- |
| `~/.config/hypr/` | `dotfiles/hypr/` |
| `~/.config/waybar/` | `dotfiles/waybar/` |
| `~/.config/wofi/` | `dotfiles/wofi/` |
| `~/.config/swaync/` | `dotfiles/swaync/` |
| `~/.config/kitty/` | `dotfiles/kitty/` |

> 💡 **Note :** Toute modification effectuée dans ce dépôt est automatiquement et immédiatement active sur le système. Les liaisons sont auditables à tout moment via `./scripts/wallpaper_tool.py check-links`.

---

## ⌨️ Raccourcis Clavier Principaux

| Raccourci | Action |
| :--- | :--- |
| <kbd>SUPER</kbd> + <kbd>Return</kbd> / <kbd>SUPER</kbd> + <kbd>Q</kbd> | Ouvrir le terminal Kitty |
| <kbd>SUPER</kbd> + <kbd>R</kbd> | Ouvrir / Fermer le lanceur d'applications (Wofi) |
| <kbd>SUPER</kbd> + <kbd>N</kbd> | Ouvrir / Fermer le centre de notifications (SwayNC) |
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
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>BackSpace</kbd> | **Arrêt d'urgence matériel IA** (`hypruse stop`) |
| <kbd>SUPER</kbd> + <kbd>&</kbd> à <kbd>à</kbd> (1-10) | Changer d'espace de travail (AZERTY) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>&</kbd> à <kbd>à</kbd> | Déplacer la fenêtre active vers un espace de travail |

### Contrôles Audio & Multimédia
- **Molette volume / Touches multimédia** : Contrôle natif du volume et lecture/pause (`wpctl`, `playerctl`).
- **Survol de la barre Spotify** : Déroulement automatique de la carte Spotify.
- **Molette sur la barre de progression Spotify** : Avancer / Reculer de 5 secondes dans le morceau.

---

## 🛠️ Utilitaires CLI & Administration

### 1. Gestion de Waybar (`hyprbar`)
```bash
hyprbar restart  # Redémarre proprement Waybar et le daemon spotify-card
hyprbar reload   # Rechargement à chaud de la configuration CSS
hyprbar toggle   # Masquer / Afficher la barre
hyprbar stop     # Arrêter la barre et la carte Spotify
hyprbar status   # Vérifier l'état et les PIDs actifs
```

### 2. Moteur de Fond d'Écran (`scripts/wallpaper_tool.py`)
```bash
./scripts/wallpaper_tool.py status       # Affiche l'état des processus, RAM (~72 Mo), CPU et couches Wayland
./scripts/wallpaper_tool.py daemon       # Lance le démon hotplug IPC (.socket2.sock)
./scripts/wallpaper_tool.py ensure       # Maintien sélectif en condition opérationnelle sur DP-1 et DP-2
./scripts/wallpaper_tool.py mask         # Régénère le masque de détourage subpixel Blackwall (blackwall_mask.png)
./scripts/wallpaper_tool.py restart      # Redémarre proprement aurora-wallpaper sous mutex sécurisé
./scripts/wallpaper_tool.py check-links  # Valide l'intégrité stricte des 42 hardlinks dotfiles/ <-> ~/.config/
```

### 3. Thémage Dynamique & Validation
```bash
# Sélecteur de thèmes d'ambiance visuelle (aurora, tokyo-night, blackwall-red, cyberpunk-amber)
python3 scripts/theme_switcher.py list
python3 scripts/theme_switcher.py status
python3 scripts/theme_switcher.py apply tokyo-night

# Harnais de test unifié zéro-régression (mode lecture seule sans réarmement runtime)
./scripts/verify_aurora.sh --read-only
```

### 4. Micro-serveur FastMCP Aurora (`aurora-mcp`)
```bash
aurora-mcp serve   # Démarrer le serveur MCP stdio pour assistants et agents IA
aurora-mcp status  # Diagnostic consolidé unifié (EGL, Waybar, Spotify, Workspaces, Moniteurs, 42 liens)
aurora-mcp audit   # Audit de conformité physique des 42 hard links
aurora-mcp reload  # Rechargement unifié de l'ensemble de la session
```

---

## 📦 Dépendances Requises

Pour faire fonctionner l'ensemble de ces fonctionnalités :

- **Composants système** : `hyprland`, `waybar`, `wofi`, `sway-notification-center` (`swaync`), `kitty`, `hyprlock`, `hypridle`, `swaybg`, `hyprpolkitagent`.
- **Moteur de fond d'écran dynamique** : `aurora-wallpaper` (Micro-moteur natif C99 / Wayland `wlr-layer-shell` + EGL/GLES2).
- **Utilitaires Wayland** : `slurp`, `grim`, `wl-clipboard` (`wl-copy`), `playerctl`, `pavucontrol`, `jq`, `wireplumber` (`wpctl`), `xrandr`, `wtype`.
- **Python & Bibliothèques** : `python3`, `python3-gi`, `python3-dbus`, `python3-pil` (Pillow).
- **Polices recommandées** : `Noto Sans`, `FontAwesome` (pour les icônes de la barre et du popup).
