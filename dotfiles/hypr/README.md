# Hyprland Configuration & Lock Protocol (`dotfiles/hypr/`) 🌌

Configuration modulaire **Lua** pour le compositeur Wayland **Hyprland 0.57.2** (`0.57.2-1ppa1`, commit `11cbc6c577b84ffb1edf4df3fc5b6128c3ae6947`), intégrant le design system **Aurora**, la gestion multi-écrans (`DP-1` et `DP-2`), les plugins C++ recompilés, l'OSD natif `aurora-osd`, le Scratchpad `code:49` et le protocole de verrouillage sécurisé.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/hypr/
├── hyprland.lua        # Configuration Lua maîtresse 0.57.2 (moniteurs, autostart, binds, règles, plugins)
├── hyprviz.lua         # Paramètres d'apparence Lua complémentaires (require("hyprviz"), blur.xray=false)
├── hypridle.conf       # Démon d'inactivité (dim 150s, lock 300s, DPMS 330s, suspend 1800s, inhibit_sleep=3)
├── hyprlock.conf       # Interface de déverrouillage graphique (champ mot de passe néon, horloge timerfd)
├── hyprlock-pam-deadlock.patch # Patch C++ prévenant le deadlock du thread PAM lors du déverrouillage
├── lock.sh             # Script de verrouillage sécurisé avec Safe Cleanup Handler (RAII)
├── scripts/
│   ├── hypr_ipc.py     # Client/serveur IPC événementiel Hyprland (.socket.sock / .socket2.sock)
│   ├── hyprlock_state.py # Gestionnaire d'état et masquage d'espaces (98 DP-2 / 99 DP-1)
│   ├── power-menu.sh   # Menu de session et d'alimentation Aurora (SUPER + S)
│   ├── reload.sh       # Script de rechargement complet (Hyprland + Waybar + SwayNC)
│   ├── screenshot.sh   # Outil de capture d'écran polyvalent (Print Screen, sélection, écran, fenêtre)
│   ├── wallpaper_daemon.sh # Lanceur du démon hotplug IPC wallpaper_daemon.py
│   ├── wofi-toggle.sh  # Lanceur d'applications Wofi avec backdrop transparent (wait -n, 0% CPU)
│   └── workspace-autocompact.py # Auto-compacteur dynamique d'espaces de travail (bornes 1-5 et 6-10)
├── plugins/
│   ├── Hyprspace.so                  # Plugin Mission Control 0.57.2 (KZdkm/Hyprspace, SUPER + TAB)
│   ├── hyprspace-multimonitor.patch  # Correctif multi-écrans (wsID < 1 || wsID >= 90 exclu en tête)
│   └── hyprglass.so                  # Plugin glassmorphism v1.2.0 recompilé 0.57.2 (hl.plugin.hyprglass)
└── theme-summer/
    └── wallpaper.jpg                 # Fond d'écran statique de secours (swaybg)
```

*(Note : `hypridle.conf` et `hyprlock.conf` conservent le format `.conf` propre aux démons `hypridle` `0.1.8` et `hyprlock` `0.9.6`, tandis que la configuration du compositeur utilise exclusivement Lua depuis `Hyprland 0.57.2` qui a supprimé `hyprlang`.)*

---

## 🧩 Architecture Lua 0.57.2, OSD Natif & Scratchpad

- **Compositeur Hyprland `0.57.2` actif en RAM** : API Lua exclusive (`hyprland.lua` `298` L + `hyprviz.lua` `26` L), zéro fichier `hyprland.conf` résiduel, `0` dépréciation (`hyprctl deprecated-config: all good!`).
- **Hooks & Directives Core `0.57.2`** :
  - Remplacement de `on_created_empty` par l'écouteur d'événements `hl.on("workspace.created", function(ws) ... end)` avec auto-spawning déterministe de `kitty --class scratchpad-term`.
  - Directives de performance et focus : `render = { use_fp16 = 0 }` (gain bande passante GPU sur dalles SDR 8-bit), `layers = { allow_new_top_layers_over_existing_fullscreen = true, layers_hog_keyboard_focus = true }`.
  - Environnement & silence : `misc = { bell_sound = "", ... }`, `ecosystem = { no_update_news = true, no_donation_nag = true }`.
- **Plugins C++ `0.57.2` sous gardes Lua** :
  - `Hyprspace.so` (`13 711 552` o, mode `775`) : configuré dans `if hl.plugin.overview then ... end` (`hl.config({ plugin = { overview = ... } })` + `hl.plugin.overview.toggle`).
  - `hyprglass.so` (`32 587 120` o, `v1.2.0`, mode `775`) : configuré via `hl.plugin.hyprglass` (`hg.config(...)` + `hg.layer("hyprlock", { preset = "clear" })`), avec exclusion de la fenêtre compagnon `Paros` (`paros-companion`, `tag = "+hyprglass_disabled"`).
- **Couches animées (`layersIn` / `layersOut`) & SwayNC** : `hl.animation` définit `layersIn` (`speed = 3`, `md3_decel`, `popin 92%`) et `layersOut` (`speed = 2`, `md3_decel`, `fade`), complétés par `hl.layer_rule` (`waybar_blur`, `wofi_blur`, `aurora_osd_blur`) et règles avec `animation = "slide right"` sur `swaync_blur` et `swaync_notif_blur`.
- **OSD Natif (`scripts/aurora_osd.py` ➔ `~/.local/bin/aurora-osd`)** : Overlay GTK3 `gtk-layer-shell` (`namespace = "aurora-osd"`, pill verre fumé `0.50`, `2px solid #00f0ff`, `17px`). Détection `capsLock` temps réel via `j/devices` (clavier `main` prioritaire) avec badge ON/OFF sans jauge, gestion de l'overdrive audio `> 100%` (`.osd-overdrive`), synchronisation dynamique de la palette via balises `# AURORA_PALETTE_START` / `# AURORA_PALETTE_END` avec `theme_switcher.py`, et neutralisation sous verrou (`is_session_locked()`).
- **Terminal Scratchpad (`special:scratchpad`)** : Règle `hl.workspace_rule` et fenêtre flottante centrée `1100 650` (`focus_on_activate = true`, `animation = "slide top"`), basculée via <kbd>SUPER</kbd> + <kbd>²</kbd> (`code:49`) ou <kbd>SUPER</kbd> + <kbd>F12</kbd>, envoi de fenêtre active via <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>²</kbd> ou <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>F12</kbd>.
- **Migration Socket1 Lua dans les scripts** :
  - `workspace-autocompact.py` : émission exclusive des dispatchers `hl.dsp.window.move({ workspace = ..., window = "address:..." })` et `hl.dsp.focus({ monitor = ... / workspace = ... })`, écoute des événements `closewindow`, `destroyworkspace`, `destroyworkspacev2`, `movewindow`, `movewindowv2`.
  - `hypr_ipc.py` : repositionnement au pixel de la carte Spotify via `dispatch hl.dsp.window.move({ x = ..., y = ..., window = "class:spotify-card" })`.
- **Écran de verrouillage optimisé (`hyprlock.conf`)** : Fond sombre `rgba(0, 0, 0, 0.30)`, `blur_passes = 0` pour zéro charge GPU idle sous verrou, horloge asservie au noyau (`timerfd`, `cmd[update:1000] date +"%H:%M"`).

---

## 🎨 Charte Visuelle Hyprland & Invariants Ergonomiques

- **Coins arrondis** : `decoration.rounding = 17` uniforme sur toutes les fenêtres et conteneurs.
- **Épaisseur de bordure** : `general.border_size = 2`.
- **Dégradé actif** : `general.col.active_border = { colors = { "rgba(00F0FFFF)", "rgba(7AA2F7FF)", "rgba(9778D0FF)", "rgba(00F0FFFF)" }, angle = 45 }` (animation `borderangle` volontairement commentée dans `hyprland.lua` pour préserver `debug.vfr = true` et zéro charge GPU idle).
- **Inactif** : `general.col.inactive_border = "rgba(04404aaa)"` discret sans halo parasite ; mise à jour dynamique *in-place* par `scripts/theme_switcher.py` (`update_hyprland_conf` / alias `update_hyprland_lua`).
- **Invariants Utilisateur (`input`)** :
  - `follow_mouse = 0` : mode Click-to-Focus strict prévenant toute perte de focus entre `DP-2` et `DP-1`.
  - `kb_layout = "fr"`, `kb_variant = ""`, `kb_model = "pc105"` : disposition AZERTY française standard sans variante altérée.

---

## 🔒 Protocole de Verrouillage & Politique Veille / DPMS (`lock.sh`)

Le script [`lock.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/lock.sh) et la configuration [`hypridle.conf`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/hypridle.conf) appliquent la politique de sécurité et de zéro écran noir sous verrouillage :

1. **Politique Veille & Extinction d'Écran (Zéro Écran Noir sous Verrou)** :
   - **Inhibition dimming (`150s`), DPMS off (`330s`) et mise en veille (`1800s`) sous verrou** : les Paliers 1, 3 et 4 de `hypridle.conf` sont tous protégés par la garde runtime :
     ```bash
     [ ! -f "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora/hypr_locked" ] && ! pgrep -x hyprlock >/dev/null
     ```
   - **Réveil DPMS & inhibition `sleep:idle`** : `lock.sh` exécute `hyprctl dispatch 'hl.dsp.dpms({ action = "on" })'` avant le verrouillage et encapsule `hyprlock` sous `systemd-inhibit --what=sleep:idle --who="Aurora Lock" --why="Session verrouillée : veille PC et écran noir désactivés" --mode=block hyprlock 9>&-`.
   - `inhibit_sleep = 3` configuré dans `general {}` de `hypridle.conf`. En session déverrouillée, la cascade complète (150s, 300s, 330s, 1800s) reste active.
2. **Masquage Dynamique & Protection Hotplug** :
   - Démon d'écoute IPC d'arrière-plan sur `.socket2.sock` actif durant toute la session verrouillée.
   - Bascule immédiate de chaque écran vers des espaces de travail vides réservés (`98` pour DP-2, `99` pour DP-1, `persistent:false`).
   - Pose du drapeau atomique `$AURORA_RUNTIME_DIR/hypr_locked` (arborescence runtime `0700`) neutralisant le démon `workspace-autocompact.py` pour empêcher tout démasquage accidentel des fenêtres.
   - En cas d'événement `monitoradded` (rallumage d'un écran) : ré-application instantanée de l'espace vide dédié et relance sélective de `aurora-wallpaper` (`wallpaper_tool.py ensure`) sans jamais redémarrer l'autre écran.
3. **Isolation Totale de Waybar** :
   - Arrêt complet du processus (`killall waybar`) et des sous-processus Spotify à l'entrée en verrouillage. Cela élimine l'artefact GTK3 où Waybar réapparaissait avec `visible = true` sur tout écran rebranché lors de l'utilisation de `SIGUSR1`.
   - Fermeture forcée des popups flottants (`wofi`, carte Spotify).
4. **Confidentialité des Notifications (SwayNC)** :
   - Mémorisation de l'état préalable, fermeture forcée du panneau (`swaync-client -cp`) et bascule immédiate en mode Ne Pas Déranger (`swaync-client -dn`).
   - Zéro toast sur l'écran de verrouillage : les alertes restent historisées en silence sans créer de couche visuelle.
5. **Restauration Déterministe Dynamique (Pattern RAII)** :
   - Routine `cleanup()` enregistrée sur tous les signaux d'interruption (`trap ... EXIT INT TERM`).
   - Restauration des workspaces d'origine **uniquement sur les moniteurs physiquement connectés** lors du déverrouillage (évite d'écraser la disposition si un écran reste éteint).
   - Rétablissement de l'état Ne Pas Déranger de SwayNC (`swaync-client -df` si inactif au départ).
   - Relance synchronisée de Waybar (`hyprctl dispatch 'hl.dsp.exec_cmd("waybar")'`) et déclenchement d'un cycle de compactage propre.
6. **Horloge Hyprlock Anti-Freeze (`hyprlock.conf`)** :
   - Remplacement de la variable passive `$TIME` (vulnérable aux race conditions internes lors des coupures DPMS) par `cmd[update:1000] date +"%H:%M"`.
   - Asservissement direct à un timer système noyau Linux (`timerfd`) garantissant un rafraîchissement d'heure déterministe à la seconde près.
7. **Résilience Multi-Processus & Détection Fiable du Verrouillage** :
   - Patch PAM natif amont (PR #1059) neutralisant le blocage récurrent du thread PAM (`std::thread::join()`) lors de la sortie de session.
   - Détection de verrouillage fiabilisée par `pgrep -x hyprlock`, acquisition non-bloquante `flock` sur `$AURORA_RUNTIME_DIR/hypr_lock_instance.lock` et présence de `$AURORA_RUNTIME_DIR/hypr_locked` (remplaçant les anciens contrôles fragiles par layer namespace).
8. **Adaptation IPC `Hyprland 0.57.2` (`lock.sh` & `hyprlock_state.py`)** :
   - La commande `keyword` ayant été retirée de l'IPC Socket1 sous `Hyprland 0.57.2`, `lock.sh` et `hyprlock_state.py` pilotent `misc:disable_autoreload` directement via `eval 'hl.config({ misc = { disable_autoreload = ... } })'`. De plus, `hyprlock_state.py` emploie la syntaxe de ciblage `hl.dsp.window.pin({ window = "address:..." })` pour épingler et détacher fidèlement les fenêtres.

---

## ⚡ Menu de Session & Alimentation (`power-menu.sh`)

Le script [`power-menu.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/power-menu.sh) déploie une boîte de dialogue d'actions rapide :
- **Raccourci** : <kbd>SUPER</kbd> + <kbd>S</kbd> (toggle : un second appui ou <kbd>Échap</kbd> referme le menu).
- **Feuille de style dédiée** : [`dotfiles/wofi/power-menu.css`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/wofi/power-menu.css) sans barre de recherche (`hide_search=true` et `#input` réduit à 0px), avec 5 capsules de verre tactiles (Verrouiller, Fermer la session, Mettre en veille, Redémarrer, Éteindre).
- **Format compact** : $300 \times 265\text{ px}$ centré à l'écran, navigation clavier ou souris.

---

## 📸 Outil de Capture d'Écran Aurora (`screenshot.sh`)

Le script [`screenshot.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/screenshot.sh) gère les captures d'écran sous Wayland :
- **Gel Instantané de l'Affichage (Freeze Screen)** : Utilisation de `hyprpicker -r -z` figeant immédiatement l'ensemble des moniteurs à l'ouverture du mode sélection. Élimine tout décalage temporel ou animation en mouvement (Lucy, vidéos, curseur) pendant le tracé de la zone.
- **Élimination Définitive des Bordures Résiduelles** : Règles de calques Lua `Hyprland 0.57.2` (`hl.layer_rule` `selection_noanim` et `hyprpicker_noanim` avec `no_anim = true`) empêchant `grim` de photographier l'estompement du cadre `slurp`.
- **Réticule Aurora affiné** : `slurp` configuré avec bordure cyan néon 1px (`#00f0ff`), fond sombre Tokyo Night semi-transparent et sécurité RAII (`trap` libérant l'affichage en cas d'annulation avec <kbd>Échap</kbd>).
- **Modes pris en charge** :
  - `area` (défaut) : Sélection interactive rectangulaire gelée (<kbd>Print</kbd> ou <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd>).
  - `screen` : Moniteur actif sous le curseur (<kbd>SHIFT</kbd> + <kbd>Print</kbd>).
  - `window` : Fenêtre sous focus actif (<kbd>SUPER</kbd> + <kbd>Print</kbd>).
  - `full` : Intégralité des écrans réunis (<kbd>CTRL</kbd> + <kbd>Print</kbd>).
- **Enregistrement & Presse-papiers** : Copie instantanée dans le presse-papiers via `wl-copy --type image/png`, sauvegarde dans `~/Images/Captures d’écran/Capture d’écran du AAAA-MM-JJ HH-MM-SS.png` et notification avec aperçu miniature (`notify-send`).

---

## ⌨️ Raccourcis Clavier Définis

| Raccourci | Action |
| :--- | :--- |
| <kbd>SUPER</kbd> + <kbd>Return</kbd> / <kbd>SUPER</kbd> + <kbd>Q</kbd> | Lancer le terminal Kitty |
| <kbd>SUPER</kbd> + <kbd>²</kbd> (`code:49`) / <kbd>SUPER</kbd> + <kbd>F12</kbd> | Afficher / Masquer le terminal Scratchpad déroulant (`special:scratchpad`) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>²</kbd> (`code:49`) / <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>F12</kbd> | Envoyer la fenêtre active vers le Scratchpad |
| <kbd>SUPER</kbd> + <kbd>C</kbd> | Fermer la fenêtre active |
| <kbd>SUPER</kbd> + <kbd>V</kbd> | Basculer la fenêtre en mode flottant |
| <kbd>SUPER</kbd> + <kbd>F</kbd> / <kbd>P</kbd> / <kbd>J</kbd> | Plein écran / Pseudo-tiling / Bascule split (`togglesplit`) |
| <kbd>SUPER</kbd> + <kbd>R</kbd> | Ouvrir / Fermer Wofi (`wofi-toggle.sh`) |
| <kbd>SUPER</kbd> + <kbd>N</kbd> | Ouvrir / Fermer le centre de notifications (`swaync-client -t -sw`) |
| <kbd>SUPER</kbd> + <kbd>S</kbd> | Menu de session et alimentation (`power-menu.sh`) |
| <kbd>Impr écran</kbd> / <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>S</kbd> | Capture d'écran (sélection rectangulaire Aurora) |
| <kbd>SHIFT</kbd> + <kbd>Impr écran</kbd> | Capture plein écran du moniteur actif |
| <kbd>SUPER</kbd> + <kbd>Impr écran</kbd> | Capture de la fenêtre active |
| <kbd>CTRL</kbd> + <kbd>Impr écran</kbd> | Capture intégrale (multi-écrans) |
| <kbd>SUPER</kbd> + <kbd>E</kbd> | Gestionnaire de fichiers (Nautilus) |
| <kbd>SUPER</kbd> + <kbd>L</kbd> | Verrouillage immédiat (`lock.sh`) |
| <kbd>SUPER</kbd> + <kbd>TAB</kbd> | Vue d'ensemble Hyprspace (Mission Control) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>R</kbd> | Recharger la configuration (`hyprctl reload`) et relancer la barre (`hyprbar restart`) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>BackSpace</kbd> | Arrêt d'urgence MCP (`hypruse stop`) |
| <kbd>XF86Audio*</kbd> / <kbd>Caps_Lock</kbd> | Contrôle volume, muet, micro et Verr. Maj via `aurora-osd` (et médias via `playerctl`) |
| <kbd>SUPER</kbd> + <kbd>&</kbd> à <kbd>à</kbd> (1-10) | Changer d'espace de travail actif |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>&</kbd> à <kbd>à</kbd> | Déplacer la fenêtre active vers l'espace de travail ciblé |
| <kbd>SUPER</kbd> + <kbd>Molette Haut / Bas</kbd> | Défiler vers l'espace de travail précédent / suivant (`e-1` / `e+1`) |
| <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>Molette</kbd> | Déplacer la fenêtre active vers l'espace précédent / suivant |

---

## 🪟 Hyprspace Mission Control & Isolation Multi-Écrans

Le plugin `Hyprspace.so` (`0.57.2`, rebasé sur `KZdkm/Hyprspace` `8345bf6`) fournit une vue d'ensemble exposé / Mission Control activable par <kbd>SUPER</kbd> + <kbd>TAB</kbd> (`hl.plugin.overview.toggle`).

Dans une configuration multi-moniteurs (`DP-2` à gauche, `DP-1` à droite) :
- **Problème d'origine** : Les workspaces inactifs ou vides fuitaient entre écrans (l'overview de l'écran droit affichait les workspaces 1 à 5 de l'écran gauche et vice versa), et les workspaces réservés de verrouillage (`98`, `99`) pouvaient court-circuiter le filtrage via leurs règles de moniteur.
- **Correctif natif C++ (`hyprspace-multimonitor.patch`)** :
  - Exclusion prioritaire en tête de `isWorkspaceForThisMonitor(wsID)` dans `src/Render.cpp` : `if (wsID < 1 || wsID >= 90) return false;` avant `getBoundMonitorStringForWS()` et `findNumberedWorkspace()`.
  - Résolution des liaisons configurées via `Config::workspaceRuleMgr()->getBoundMonitorStringForWS()`.
  - Bornes dynamiques par moniteur garantissant l'isolation stricte (`1` à `5` sur `DP-2`, `6` à `10` sur `DP-1`).

---

## ⚙️ Maintenance & Rechargement

```bash
# Valider la syntaxe Lua Hyprland 0.57.2 sans recharger la session
Hyprland --config ~/.config/hypr/hyprland.lua --verify-config

# Recharger la configuration Hyprland à chaud
hyprctl reload

# Vérifier les hardlinks et la syntaxe des scripts
python3 -B tests/test_audit_hardlinks.py
bash -n dotfiles/hypr/lock.sh dotfiles/hypr/scripts/wofi-toggle.sh
```
