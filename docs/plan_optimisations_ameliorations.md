# Synthèse de Diagnostic et Plan d'Optimisations & Améliorations — Aurora OS

**Auteur** : Architecte (Équipe Zygos)  
**Projet** : Hyperland (`/home/user/Documents/antigravity/hyprland_project`)  
**Tâche** : T3 — Synthèse de diagnostic et feuille de route des Jalons 2 et 3  
**Date** : jeu. 12 nov. 2026 15:21:17 CET  
**Statut** : Validé pour passage au Chef & attribution au Programmeur  

---

## 1. Consolidation des Audits T1 & T2

Les audits approfondis menés sur la branche `dev` (T1 pour les démons IPC et le verrouillage ; T2 pour le sous-système multimédia, Waybar et les scripts utilitaires) confirment la conformité volumétrique de tous les fichiers sources (< 500 lignes) et l'intégrité de la charte esthétique Aurora (rayon 17px, bordures 2px, dégradé néon 45°).

Cependant, ils mettent en lumière plusieurs faiblesses architecturales, goulots d'étranglement de performance et vulnérabilités de synchronisation.

### 1.1 Matrice Consolidée des Goulots d'Étranglement et Failles

| Réf. | Composant / Script | Domaine | Métrique / Constat Observé | Impact & Gravité |
| :--- | :--- | :--- | :--- | :--- |
| **G-01** | `dotfiles/waybar/scripts/gpu.py` | CPU / Performance | 19.86 ms par scan (295 PIDs, 3903 FDs parcourus toutes les 3 s) ; 1.2% CPU continu | **Moyenne** : Surconsommation inutile de cycles CPU sur un composant passif de barre de statut. |
| **G-02** | `dotfiles/hypr/scripts/workspace-autocompact.py` | IPC / Résilience | Socket `hypr_cmd()` bloquant sans timeout ; auto-déclenchement écho sur `movewindow` | **Moyenne** : Risque de gel indéfini du démon et 4 requêtes socket IPC superflues par cycle. |
| **G-03** | `dotfiles/hypr/scripts/workspace-autocompact.py` | Multi-Écran | Déconnexion DP-1 entraîne le compactage destructif des espaces 6–10 dans 1–3 sur DP-2 | **Élevée** : Perte de la disposition utilisateur lors des événements de débranchement d'écran. |
| **G-04** | `dotfiles/hypr/scripts/hyprlock_state.py` | Concurrence / IPC | `run_watcher()` bloqué dans `s.recv()` synchrone ; aucun debounce d'`enforce_lock()` | **Élevée** : Processus watcher potentiellement orphelin ; tempête de batchs IPC lors d'ouvertures fenêtres. |
| **G-05** | `dotfiles/hypr/scripts/hyprlock_state.py` | Hotplug Écran | Écran branché pendant le verrouillage absent d'`orig` dans `restore_state()` | **Critique** : Écran secondaire bloqué indéfiniment sur l'espace fantôme 97 après déverrouillage. |
| **G-06** | `dotfiles/hypr/lock.sh` | Sécurité Visuelle | Waybar killé après `switch-reserved` ; SwayNC DND lancé en tâche de fond `&` | **Moyenne** : Fenêtre de fuite visuelle de 50 à 100 ms affichant la barre et les popups sous verrou. |
| **G-07** | `dotfiles/hypr/hypridle.conf` | Énergie / Dalles | Un seul palier (300 s : lock) ; aucun DPMS off d'extinction écran ; aucun suspend | **Élevée** : Dalles IPS/OLED allumées indéfiniment à pleine intensité sous verrouillage ; pas de veille profonde. |
| **G-08** | `dotfiles/hypr/hyprlock.conf` | Sécurité Défensive | Fond 50% translucide sans flou (`blur_passes = 0`) | **Moyenne** : Dépendance critique envers l'IPC. Si le switch d'espace échoue, les fenêtres restent lisibles. |
| **G-09** | `scripts/hyprbar` | Hygiène Processus | `pkill -9 -f "spotify-card.py"` brutal ; `sleep 0.3` fixe lors du redémarrage | **Faible** : Risque de corruption de socket UNIX `/tmp/spotify_card.sock` et collision de ports GTK/SSE. |
| **G-10** | `dotfiles/hypr/scripts/screenshot.sh` | Robustesse | Dépendance `swappy` absente sans avertissement si mode édition invoqué | **Faible** : Échec silencieux potentiel lors des tentatives d'annotation interactive. |

---

## 2. Jalon 2 : Plan d'Optimisations de Performance & Résilience

Le Jalon 2 traite l'éradication des goulots d'étranglement et le durcissement complet des démons et de la chaîne de verrouillage.

```
       JALON 2 : STABILISATION & DURCISSEMENT
       +-----------------------------------------------+
       | Opt-1 : Fast-Path DRM gpu.py (< 2ms, < 0.2%)  |
       +-----------------------------------------------+
       | Opt-2 : IPC & Rollback autocompact.py         |
       +-----------------------------------------------+
       | Opt-3 : Non-blocking Watcher & Hotplug Fix    |
       +-----------------------------------------------+
       | Opt-4 : Lock.sh atomique & Hypridle DPMS      |
       +-----------------------------------------------+
       | Opt-5 : Hygiène signaux hyprbar & screenshot  |
       +-----------------------------------------------+
```

### 2.1 Lot Opt-1 — Optimisation du Moniteur GPU (`gpu.py`)
- **Fichier** : `dotfiles/waybar/scripts/gpu.py` (269 lignes).
- **Problème** : `sample_drm_clients()` itère sur tous les PIDs de `/proc` (295 processus) et résout tous leurs descripteurs de fichiers (`os.readlink()` sur 3903 fichiers), consommant 19.86 ms et 1.2% de CPU fixe toutes les 3 secondes.
- **Spécifications Techniques pour le Programmeur** :
  1. *Cache des PIDs clients DRM* : Maintenir un ensemble `_cached_drm_pids: set[str]` et un horodatage de rafraîchissement.
  2. *Stratégie Bi-Cadence* :
     - *Scan rapide (Fast-Path)* : À chaque cycle de 3 secondes, scanner uniquement les répertoires `/proc/{pid}/fd` des PIDs en cache (~5 à 10 processus graphiques réels : Hyprland, Xwayland, Kitty, navigateur).
     - *Scan complet de découverte (Slow-Path)* : Ne parcourir l'ensemble de `/proc` que toutes les 30 secondes (1 cycle sur 10) ou si un PID en cache disparaît.
  3. *Critères d'acceptation* :
     - Temps moyen d'échantillonnage ramené de ~20 ms à $< 2$ ms (réduction de 90%).
     - Charge CPU du processus Waybar GPU ramenée de 1.2% à $< 0.2%$.
     - Préservation exacte du payload JSON Waybar et de la compatibilité hardlink.

### 2.2 Lot Opt-2 — Durcissement d'IPC & Multi-Écran (`workspace-autocompact.py`)
- **Fichier** : `dotfiles/hypr/scripts/workspace-autocompact.py` (338 lignes).
- **Problème** : Socket de commande sans timeout ; effet d'écho relançant une passe inutile 80 ms après chaque compactage ; compactage écrasant les espaces réservés en cas d'absence d'écran.
- **Spécifications Techniques pour le Programmeur** :
  1. *Timeouts Socket* : Dans `hypr_cmd()`, appliquer `s.settimeout(1.0)` avant `s.connect()`.
  2. *Drain du tampon d'événements* : À l'issue de `compact_workspaces()`, vider les événements résiduels `movewindow` accumulés dans le socket noyau pour supprimer la 2e passe fantôme.
  3. *Reconnexion robuste* : En cas de coupure du compositeur, invalider `HYPRLAND_INSTANCE_SIGNATURE` si la connexion échoue 3 fois et rescanner le répertoire le plus récent par `mtime`.
  4. *Préservation Multi-Écran* : Dans `compact_workspaces()`, si un moniteur configuré (DP-1) est absent de `j/monitors`, ne pas réassigner ses espaces (6–10) au moniteur restant (DP-2). Isoler strictement les pools d'espaces.
  5. *Critères d'acceptation* : Zéro boucle d'écho mesurée après réarrangement ; reconnexion automatique vérifiée après redémarrage d'Hyprland ; conservation des espaces 6+ lors du retrait de DP-1.

### 2.3 Lot Opt-3 — Surveillance Non-Bloquante & Hotplug (`hyprlock_state.py`)
- **Fichier** : `dotfiles/hypr/scripts/hyprlock_state.py` (304 lignes).
- **Problème** : `run_watcher()` bloqué dans `recv()` synchrone ; bug d'abandon d'écran sur l'espace 97 après hotplug sous verrouillage ; absence de debounce sur `enforce_lock()`.
- **Spécifications Techniques pour le Programmeur** :
  1. *Boucle d'Événements Non-Bloquante* :
     - Configurer le socket en mode non-bloquant `s.setblocking(False)`.
     - Utiliser `select.select([s], [], [], 0.5)` dans la boucle `while os.path.exists(LOCK_FILE)`.
     - Permettre au watcher de détecter la disparition de `LOCK_FILE` et de s'arrêter proprement même en l'absence d'événement compositeur.
  2. *Debounce d'Enforcement* : Regrouper les événements IPC (`workspace`, `focusedmon`, `openwindow`) avec un debounce de 50 ms avant d'appeler `enforce_lock()`.
  3. *Correction Critique Hotplug dans `restore_state()`* :
     - Si un écran présent dans `j/monitors` n'a pas d'entrée dans `STATE_FILE` (branché pendant la veille), lui affecter un espace sain par défaut (espace 1 pour DP-2, espace 6 pour DP-1, ou premier espace non verrouillé) au lieu de le laisser sur 97.
  4. *Critères d'acceptation* : Détection immédiate du déverrouillage par le watcher ; écran branché à chaud sous verrouillage restauré sur un espace utilisateur valide dès le déverrouillage.

### 2.4 Lot Opt-4 — Sécurisation Atomique de Verrouillage & Veille (`lock.sh`, `hypridle.conf`, `hyprlock.conf`)
- **Fichiers** :
  - `dotfiles/hypr/lock.sh` (90 lignes).
  - `dotfiles/hypr/hypridle.conf` (10 lignes).
  - `dotfiles/hypr/hyprlock.conf` (84 lignes).
- **Problème** : Fenêtre temporelle de fuite visuelle Waybar/SwayNC ; absence d'extinction DPMS et de veille système ; fond 50% translucide sans flou de repli.
- **Spécifications Techniques pour le Programmeur** :
  1. *Séquencement Synchrone dans `lock.sh`* :
     - Exécuter la suspension SwayNC DND (`swaync-client -dn -sw`) et l'arrêt de Waybar de manière synchrone *avant* le lancement de `hyprlock`.
     - Garantir que l'écran est net de tout élément d'interface avant la prise de contrôle par hyprlock.
  2. *Étagement Énergétique dans `hypridle.conf`* :
     - `listener 1` (150 s) : Baisse préventive de luminosité (`brightnessctl -s set 20%`).
     - `listener 2` (300 s) : Verrouillage session (`loginctl lock-session`).
     - `listener 3` (330 s) : Extinction moniteurs (`hyprctl dispatch dpms off`), rallumage sur activité (`on-resume = hyprctl dispatch dpms on`).
     - `listener 4` (1800 s) : Mise en veille profonde (`systemctl suspend`).
     - `general` : Ajouter `after_sleep_cmd = hyprctl dispatch dpms on`.
  3. *Flou Protecteur dans `hyprlock.conf`* :
     - Conserver l'ambiance translucide tout en configurant `blur_passes = 2` et `blur_size = 6` sur le composant `background`.
     - Éliminer le risque de divulgation de texte confidentiel même en cas d'anomalie d'isolation d'espace.
  4. *Critères d'acceptation* : Disparition instantanée de Waybar avant hyprlock ; extinction effective des dalles à 330 s ; fond dépoli empêchant la lecture d'une fenêtre résiduelle.

### 2.5 Lot Opt-5 — Assainissement des Utilitaires (`hyprbar`, `screenshot.sh`)
- **Fichiers** :
  - `scripts/hyprbar` (58 lignes).
  - `dotfiles/hypr/scripts/screenshot.sh` (86 lignes).
- **Problème** : Signaux SIGKILL brutaux sans délai de grâce ; collision de port SSE lors du restart ; absence d'avertissement si swappy requis.
- **Spécifications Techniques pour le Programmeur** :
  1. *Hygiène des Signaux dans `scripts/hyprbar`* :
     - Remplacer `pkill -9 -f "spotify-card.py"` par un signal gracieux `pkill -TERM -f "spotify-card.py"`.
     - Mettre en place une boucle d'attente active bornée (jusqu'à 1.0 s) testant la libération du socket `/tmp/spotify_card.sock` et du port 8975 avant de relancer le démon.
     - N'invoquer `SIGKILL` qu'en ultime recours après expiration du délai.
  2. *Tolérance aux Dépendances dans `screenshot.sh`* :
     - Vérifier la présence de `swappy` lors d'un appel avec option d'édition.
     - En l'absence de `swappy`, basculer silencieusement sur la copie presse-papiers directe avec notification explicite : `"Capture effectuée (swappy non installé)"`.
  3. *Critères d'acceptation* : Redémarrage de Waybar sans socket orphelin ; arrêt propre des widgets GTK ; aucune erreur Bash sur screenshot.

---

## 3. Jalon 3 : Améliorations à Valeur Ajoutée (Features)

Le Jalon 3 enrichit l'expérience utilisateur et l'outillage de contrôle qualité sans alourdir le système.

```
       JALON 3 : AMÉLIORATIONS À VALEUR AJOUTÉE
       +-----------------------------------------------+
       | Feat-1 : Pre-commit Hook (Hardlinks & < 500l) |
       +-----------------------------------------------+
       | Feat-2 : Notifications Riches SwayNC (Thèmes) |
       +-----------------------------------------------+
       | Feat-3 : Mode Low-Power Aurora Wallpaper      |
       +-----------------------------------------------+
```

### 3.1 Lot Feat-1 — Intégration & Activation du Hook Pre-Commit Git
- **Fichiers** : `hooks/pre-commit` (92 lignes) et `.git/hooks/pre-commit`.
- **Objectif** : Empêcher toute régression dans le dépôt partagé (rupture de hardlinks physiques, dépassement du plafond de 500 lignes, erreurs de syntaxe).
- **Spécifications Techniques pour le Programmeur** :
  1. *Actualisation du Décompte Hardlinks* :
     - Mettre à jour `hooks/pre-commit` pour valider l'ensemble des 42 hardlinks nominaux réels répertoriés par le testeur (au lieu des 39 historiques).
     - Remplacer l'appel rigide à `wallpaper_tool.py` par l'exécution de la suite de test certifiée `tests/test_audit_hardlinks.py`.
  2. *Contrôle Volumétrique Renforcé* :
     - Rejeter tout commit introduisant un fichier de code $\ge 500$ lignes.
     - Émettre un avertissement préventif (Warning) dès $\ge 400$ lignes pour inciter au découpage SRP.
  3. *Validation Bilingue* :
     - `python3 -m py_compile` sur tous les fichiers `.py` indexés.
     - `bash -n` sur tous les scripts `.sh` indexés.
  4. *Activation* : S'assurer de la présence et des droits d'exécution du lien symbolique `.git/hooks/pre-commit -> ../../hooks/pre-commit`.

### 3.2 Lot Feat-2 — Notifications Riches SwayNC lors des Changements de Thèmes
- **Fichier** : `scripts/theme_switcher.py` (294 lignes).
- **Objectif** : Offrir un retour visuel moderne et immersif lors de l'application d'un thème d'ambiance visuelle (Cyberpunk, Summer, Neon, Dark, etc.).
- **Spécifications Techniques pour le Programmeur** :
  1. *Génération de Notification GTK / SwayNC* :
     - À la fin de `apply_theme()`, invoquer `notify-send` via `subprocess.run()`.
     - Paramètres requis :
       * App name : `"Aurora Theme"` (`-a "Aurora Theme"`).
       * Titre : `f"Thème d'ambiance : {profile.display_name}"`.
       * Corps : Aperçu de la palette (codes hexadécimaux primaire, secondaire, accent) et confirmation des composants synchronisés (Waybar, SwayNC, Kitty, Hyprland).
       * Urgence : Normale (`-u normal`), expiration 3500 ms (`-t 3500`).
  2. *Intégration Blacklist SwayNC* :
     - Vérifier que la notification n'est pas bloquée par les règles de filtrage de SwayNC (`dotfiles/swaync/config.json`).
  3. *Volumétrie* : L'implémentation doit ajouter au maximum 25 à 30 lignes pour maintenir `theme_switcher.py` confortablement sous les 350 lignes (plafond 500).

### 3.3 Lot Feat-3 — Mode Low-Power Automatique pour `aurora-wallpaper`
- **Fichier** : `src/aurora_wallpaper/main.c` (396 lignes).
- **Objectif** : Réduire l'empreinte énergétique du fond d'écran animé en adaptant la cadence de rendu lors des phases d'inactivité ou sur batterie.
- **Spécifications Techniques pour le Programmeur** :
  1. *Détection d'État Énergétique & Inactivité* :
     - Vérifier l'existence du drapeau de verrouillage `$AURORA_RUNTIME_DIR/hypr_locked`.
     - Détecter l'état de décharge batterie via `/sys/class/power_supply/BAT*/status` (si présent).
  2. *Adaptation Dynamique du Framerate* :
     - *Mode Nominal (Actif)* : 30 FPS fixes (`frame_duration_us = 33333`).
     - *Mode Batterie (Économie)* : 15 FPS (`frame_duration_us = 66666`).
     - *Mode Session Verrouillée (Veille)* : 1 FPS (`frame_duration_us = 1000000`) ou mise en pause complète du rendu OpenGL / EGL avec attente bloquante sur événement Wayland via `poll()`.
  3. *Garde-Fou Volumétrique* : `main.c` compte actuellement 396 lignes. L'ajout du mode basse consommation doit être compact (< 30 lignes) ou factorisé dans `gl_utils.c` pour ne pas franchir le seuil d'alerte des 400 lignes.

---

## 4. Règles Architecturales & Stratégie d'Exécution

1. **Règle de Séparation Stricte (SRP & Rôles)** :
   - L'Architecte valide l'architecture, les interfaces et les contrats.
   - Le Programmeur produit le code technique dans `src/`, `scripts/` et `dotfiles/`.
   - Le Testeur certifie les métriques avant/après par mesures triplées.
2. **Plafond Volumétrique Absolu (< 500 Lignes)** :
   - Aucun fichier modifié ne doit dépasser 500 lignes.
   - Attention particulière portée sur `src/aurora_wallpaper/main.c` (actuellement à 396 lignes) et `scripts/theme_switcher.py` (294 lignes).
3. **Immutabilité des Hardlinks** :
   - Toute mise à jour de fichier dans `dotfiles/` doit impérativement préserver l'inode sous peine de briser la synchronisation avec `~/.config/`.
   - Validation systématique par `python3 tests/test_audit_hardlinks.py` (42/42 liens intègres).

---

## 5. Synthèse & Ordonnancement Recommandé

L'ordonnancement optimal des travaux pour le Master/Chef est :
1. **Étape 1 (Jalon 2 - Performance immédiate)** : Attribution du lot **Opt-1** (`gpu.py`) pour diviser immédiatement par 6 la charge CPU du moniteur GPU.
2. **Étape 2 (Jalon 2 - Robustesse IPC)** : Attribution des lots **Opt-2** et **Opt-3** (`workspace-autocompact.py` et `hyprlock_state.py`) pour éliminer les bugs de blocage et de hotplug écran.
3. **Étape 3 (Jalon 2 - Sécurité & Utilitaires)** : Attribution des lots **Opt-4** et **Opt-5** (`lock.sh`, `hypridle.conf`, `hyprbar`, `screenshot.sh`).
4. **Étape 4 (Jalon 3 - Contrôle & Features)** : Déploiement de **Feat-1** (Pre-commit hook), **Feat-2** (SwayNC) et **Feat-3** (Low-Power wallpaper).
