# Rapport d'Audit Technique Approfondi — Démons IPC Hyprland & Chaîne de Verrouillage

**Auteur** : Architecte (Équipe Zygos)  
**Projet** : Hyperland (`/home/user/Documents/antigravity/hyprland_project`)  
**Tâche** : T1 — Audit des démons IPC Hyprland et de la chaîne de verrouillage  
**Date** : jeu. 12 nov. 2026 15:13:43 CET  
**Statut** : Validé / Prêt pour implémentation Programmeur  

---

## 1. Périmètre & Méthodologie d'Audit

L'audit analyse en profondeur les démons d'arrière-plan communicant via l'IPC Hyprland ainsi que la chaîne complète de mise en veille et verrouillage de session :
- **Compacteur dynamique d'espaces de travail** : `dotfiles/hypr/scripts/workspace-autocompact.py` (338 lignes).
- **Gestionnaire d'état de verrouillage et d'isolation d'espaces** : `dotfiles/hypr/scripts/hyprlock_state.py` (304 lignes).
- **Script orchestrateur de verrouillage** : `dotfiles/hypr/lock.sh` (90 lignes).
- **Configuration du démon d'inactivité** : `dotfiles/hypr/hypridle.conf` (10 lignes).
- **Configuration de la surface de verrouillage** : `dotfiles/hypr/hyprlock.conf` (84 lignes).
- **Patch de stabilité PAM** : `dotfiles/hypr/hyprlock-pam-deadlock.patch` (163 lignes).

### Conformité Volumétrique (< 500 Lignes)
Tous les fichiers inspectés respectent strictement le plafond absolu de 500 lignes imposé par Zygos. Le présent rapport d'architecture s'y conforme également avec un dimensionnement ciblé (~400 lignes).

---

## 2. Audit de `workspace-autocompact.py`

Le script assure le compactage sans trou des numéros d'espaces de travail par moniteur (DP-2 gauche : 1 à 5 ; DP-1 droite : 6 à 10).

```
                      +-----------------------------+
                      | Hyprland (socket2.sock)    |
                      +--------------+--------------+
                                     | Événements (closewindow, destroyworkspace, movewindow)
                                     v
                      +-----------------------------+
                      | workspace-autocompact.py    |
                      | Debounce (80ms) + Mutex Lock |
                      +--------------+--------------+
                                     | Re-dispatches ([[BATCH]])
                                     v
                      +-----------------------------+
                      | Hyprland (.socket.sock)     |
                      +-----------------------------+
```

### 2.1 Connexion IPC & Résolution des Sockets
- **Mécanisme** : `get_hypr_socket_paths()` lit `$XDG_RUNTIME_DIR` et `$HYPRLAND_INSTANCE_SIGNATURE` pour localiser `.socket.sock` (commandes) et `.socket2.sock` (flux d'événements). En secours, il inspecte `$XDG_RUNTIME_DIR/hypr/` et trie les répertoires candidats par date de modification (`mtime`).
- **Anomalie 1.1 — Blocage infini sur ancienne instance lors du redémarrage du compositeur** :
  Si Hyprland plante et redémarre avec une nouvelle signature d'instance, `os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")` hérité au démarrage du démon conserve l'ancienne valeur. Si l'ancien répertoire n'est pas purgé par le système, `os.path.exists()` renvoie `True` sur des sockets zombies. Le démon boucle alors indéfiniment en échec de connexion (`s.connect` -> `sleep 1.0`) sans jamais basculer sur la recherche par `mtime`.
  *Recommandation* : En cas d'échec répété de connexion (ex. 3 essais), invalider la signature en cache d'environnement et forcer la redécouverte du socket le plus récent.
- **Anomalie 1.2 — Absence de délai d'expiration (timeout) sur le socket de commande** :
  Dans `hypr_cmd()`, la socket AF_UNIX est créée sans `s.settimeout()`. Si Hyprland est ralenti ou subit un blocage partiel, l'appel `s.recv(4096)` devient bloquant indéfiniment, paralysant l'ensemble du démon d'arrière-plan.
  *Recommandation* : Ajouter `s.settimeout(1.0)` comme dans `hyprlock_state.py`.

### 2.2 Concurrence, Événements & Débouncing
- **Débouncing actuel** : `debounce_delay = 0.08` (80 ms) sur `closewindow`, `destroyworkspace` et `movewindow`.
- **Anomalie 1.3 — Effet d'écho et déclenchement redondant (Self-Triggering Loop)** :
  Lorsque `compact_workspaces()` réarrange des fenêtres, il émet des instructions batch `movetoworkspacesilent`. Le compositeur émet en réponse autant d'événements `movewindow` sur `socket2.sock`. Pendant l'exécution de `compact_workspaces()`, le tampon noyau du socket accumule ces messages. Dès la fin de la fonction (`is_compacting = False`), `select.select()` dépile ces événements qui réarment un nouveau compactage 80 ms plus tard. Bien que la 2e passe ne modifie rien (état déjà stable), cela engendre 4 requêtes socket IPC inutiles par compactage.
  *Recommandation* : Vider le tampon résiduel du socket (drain) immédiatement après l'exécution de `compact_workspaces()`.
- **Anomalie 1.4 — Perte d'événements concurrents pendant le compactage** :
  Si un événement légitime (`closewindow`) survient exactement pendant les 20 à 40 ms où `compact_workspaces()` s'exécute, il est ignoré car `is_compacting` est actif (`if not is_compacting and event_name in ...`). Cet événement ne réarmera pas de compactage ultérieur.
  *Recommandation* : Remplacer le booléen `is_compacting` par un drapeau `recompact_requested_during_run = True` s'il reçoit un événement critique en cours de traitement.

### 2.3 Logique Multi-Écrans, Moniteur Unique & Hotplug
- **Configuration figée** :
  `configs = {"DP-2": {"base": 1, "max": 5}, "DP-1": {"base": 6, "max": 10}}`
  Les règles dynamiques lues via `j/workspacerules` viennent enrichir cette structure.
- **Anomalie 1.5 — Régression lors du débranchement d'un écran secondaire** :
  Si DP-1 est déconnecté, Hyprland migre les fenêtres des espaces 6–10 vers l'écran restant (DP-2). `get_ws_monitor(ws_id)` identifie désormais DP-2 comme moniteur de ces fenêtres. Comme `configs["DP-2"]["base"] == 1`, l'algorithme compacte immédiatement les espaces [1, 2, 6] en [1, 2, 3].
  Lors de la reconnexion de DP-1, les fenêtres restent compactées sur l'écran principal au lieu de reprendre leur position sur la base 6.
  *Recommandation* : Détecter le nombre réel d'écrans actifs. Si un moniteur configuré est absent de `mon_info_map`, préserver ses espaces réservés sans les fusionner agressivement dans le pool de l'écran principal.
- **Anomalie 1.6 — Écrans tiers non reconnus** :
  Tout écran non nommé DP-1/DP-2 et sans règle explicite dans `j/workspacerules` (ex. `HDMI-A-1` ou `eDP-1`) est ignoré par `compact_workspaces()`.

---

## 3. Audit de `hyprlock_state.py`

Ce composant gère l'isolation visuelle avant verrouillage : sauvegarde des espaces actifs, bascule des écrans sur les espaces vides réservés (98 sur DP-2, 99 sur DP-1, 97 sur les autres), expulsion des fenêtres parasites et restauration au déverrouillage.

```
       [Avant Verrouillage]                     [Après Déverrouillage]
DP-2: Actif -> Espace 98 (vide)    =====>   DP-2: Espace 98 -> Espace d'origine
DP-1: Actif -> Espace 99 (vide)    =====>   DP-1: Espace 99 -> Espace d'origine
Fenêtres résiduelles -> Expulsées           Focus moniteur restauré fidèlement
```

### 3.1 Synchronisation & Capture d'État
- **Fichier d'état** : `$AURORA_RUNTIME_DIR/hypr_lock_orig_workspaces.json` (au sein de l'arborescence sécurisée `${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora`, mode `0700`).
- **Points forts** :
  - `save_state()` intègre une protection récursive : si l'espace actuel est déjà 97, 98 ou 99 (cas d'un appel répété sous verrouillage), il conserve la valeur antérieure ou applique un repli sain (1 pour DP-2, 6 pour DP-1).
  - Préservation du moniteur ayant le focus via la clé `__focused__`.
  - Exclusion explicite du widget compagnon `Paros` dans `expel_clients()`.

### 3.2 Défaillances du Démon d'Écoute (`run_watcher`)
- **Anomalie 2.1 — Blocage indéfini dans `s.recv()` sur socket bloquant** :
  Dans `run_watcher()`, le socket connecté à `event_sock_path` est créé en mode bloquant standard, sans `s.settimeout()` ni `select.select()`.
  La boucle `while os.path.exists(LOCK_FILE):` ne teste la suppression du fichier qu'au réveil de `s.recv(4096)`. En l'absence d'événement IPC émis par le compositeur, le thread reste bloqué dans l'appel système `recv()`.
  Bien que `lock.sh` effectue un `kill $WATCHER_PID`, en cas d'interruption anormale ou de défaillance du signal, le processus persiste en arrière-plan.
  *Recommandation* : Utiliser un socket non-bloquant avec `select.select([s], [], [], 0.5)` pour réévaluer périodiquement `LOCK_FILE` et terminer proprement sans dépendre d'un événement externe.
- **Anomalie 2.2 — Absence de temporisation (Debounce) et cascade de requêtes IPC** :
  Pour chaque ligne reçue correspondant à `workspace`, `workspacev2`, `focusedmon`, `openwindow` ou `mapwindow`, `run_watcher()` appelle immédiatement `enforce_lock()`.
  `enforce_lock()` exécute 2 connexions IPC synchrones (`j/monitors` et `j/clients`), puis potentiellement un batch de bascule d'espace. Ce batch émet de nouveaux événements `workspace`, créant une tempête d'appels IPC synchrones.
  *Recommandation* : Introduire un délai d'apaisement (debounce de 50 ms) avant d'invoquer `enforce_lock()`.

### 3.3 Gestion Multi-Moniteurs & Hotplug sous Verrouillage
- **Anomalie 2.3 — Défaut critique de restauration lors d'un branchement à chaud** :
  Lors de la détection de `monitoradded`, le watcher force le nouvel écran sur l'espace 97 via `enforce_lock()`.
  Cependant, `STATE_FILE` (créé lors du verrouillage initial) ne contient aucune entrée pour cet écran.
  Lors du déverrouillage, `restore_state()` parcourt les moniteurs connectés et n'applique la restauration que `if name in orig:`.
  Le moniteur branché pendant le verrouillage n'est jamais restauré : il reste définitivement bloqué sur l'espace fantôme 97 !
  *Recommandation* : Dans `restore_state()`, si un écran connecté n'est pas présent dans `orig`, lui assigner explicitement un espace par défaut valide (espace 1 pour DP-2, 6 pour DP-1, ou son premier espace configuré) plutôt que de l'abandonner sur 97.
- **Anomalie 2.4 — Déconnexion d'écran non surveillée** :
  `run_watcher()` n'écoute pas l'événement `monitorremoved`. Si un écran est débranché pendant le verrouillage, les fenêtres qui y étaient associées ne font pas l'objet d'une vérification d'isolation.

---

## 4. Audit de la Chaîne Complète de Verrouillage

### 4.1 Script Orchestrateur `lock.sh`
- **Mécanismes de sécurité exemplaires** :
  1. *Mutex singleton atomique* : `exec 9>"$INSTANCE_LOCK"` suivi de `flock -n 9`. Impossible de lancer deux verrous concurrents.
  2. *Élimination des processus orphelins* : `pidof hyprlock` entraîne un nettoyage préventif.
  3. *Gestionnaire RAII complet* : `trap cleanup EXIT INT TERM` garantit la restauration de l'état même en cas de crash ou signal SIGTERM.
  4. *Désactivation de l'autoreload* : `hyprctl keyword misc:disable_autoreload true` prévient toute réinitialisation intempestive de la disposition suite à une modification de configuration pendant le verrouillage.

```
       lock.sh (flock mutex)
             |
             +---> 1. hyprctl disable_autoreload true
             +---> 2. hyprlock_state.py save
             +---> 3. hyprlock_state.py switch-reserved (98, 99)
             +---> 4. hyprlock_state.py watch &
             +---> 5. SwayNC DND On & close panel (& asynchrone)
             +---> 6. Killall waybar, spotify, gpu
             +---> 7. hyprlock_state.py expel-clients
             +---> 8. hyprlock (bloquant)
             |
       [Déverrouillage]
             |
             +---> cleanup() (trap RAII) :
                   - Kill watcher
                   - Restore disable_autoreload false
                   - hyprlock_state.py restore
                   - Relance Waybar
                   - Restauration DND SwayNC
```

- **Anomalie 3.1 — Fenêtre de vulnérabilité temporelle (Race Condition) sur le masquage de Waybar et SwayNC** :
  Dans `lock.sh`, la bascule vers les espaces 98/99 a lieu à la ligne 62, mais Waybar n'est arrêté qu'à la ligne 77 via `killall waybar`. De plus, les commandes `swaync-client -cp` (fermeture panneau) et `swaync-client -dn` (activation DND) sont lancées en arrière-plan sans attendre leur achèvement (`&`).
  Pendant 50 à 100 ms, Waybar et les notifications SwayNC restent affichées au-dessus des espaces de travail réservés avant que `hyprlock` ne prenne la main.
  *Recommandation* : Fermer les notifications et tuer Waybar *avant* ou de façon strictement synchrone avec le basculement d'espaces.

### 4.2 Démon d'Inactivité `hypridle.conf`
- **Configuration actuelle** :
```ini
general {
    lock_cmd = /home/user/.config/hypr/lock.sh
    before_sleep_cmd = loginctl lock-session
}

listener {
    timeout = 300 # 5 min d'inactivité
    on-timeout = loginctl lock-session
}
```
- **Anomalie 3.2 — Absence critique de gestion énergétique progressive (DPMS & Veille profonde)** :
  La configuration ne comporte qu'un unique palier à 300 s qui verrouille la session.
  1. *Aucune extinction d'écran (DPMS off)* : Une fois verrouillés, les écrans restent allumés à 100 % de luminosité indéfiniment (risque de marquage pour les dalles OLED/IPS et surconsommation).
  2. *Aucune veille profonde (Suspend to RAM)* : Le système ne bascule jamais en veille automatique (`systemctl suspend`).
  3. *Aucun avertissement préalable (Dimming)* : Pas de baisse de luminosité 30 s avant le verrouillage.
  4. *Manque de `after_sleep_cmd`* : En sortie de veille système, aucun appel `hyprctl dispatch dpms on` n'est configuré dans `general`.
  *Recommandation & Décision P1* : Structurer `hypridle.conf` en cascade multi-niveaux articulée avec la décision utilisateur `P1` :
  - 150 s : Dimming écran (`brightnessctl` ou avertissement visuel).
  - 300 s : Verrouillage (`loginctl lock-session`).
  - 330 s : Extinction des écrans DPMS off maintenue (`hyprctl dispatch dpms off`, réveil sur `dpms on`).
  - 1800 s : Mise en veille système (`systemctl suspend`), **strictement inhibée pendant le verrouillage** via `systemd-inhibit --what=sleep` et garde conditionnelle `hypridle.conf`.

### 4.3 Surface de Verrouillage `hyprlock.conf`
- **Configuration esthétique** :
```ini
background {
    color = rgba(9, 7, 39, 0.50)
    blur_passes = 0
}
```
- **Anomalie 3.3 — Dépendance critique de sécurité liée à la translucidité (0.50)** :
  Le fond de `hyprlock` est volontairement translucide à 50 % avec zéro flou (`blur_passes = 0`) afin de laisser paraître les fonds animés d'Aurora.
  Par conséquent, `hyprlock` ne constitue pas une barrière visuelle opaque par lui-même. Si l'isolation d'espace (`hyprlock_state.py`) échoue, les fenêtres utilisateur sont directement lisibles à travers le verrou.
  *Recommandation architecturale* : Maintenir le couplage fort entre `lock.sh` et `hyprlock_state.py`. En guise de sécurité intrinsèque, ajouter un `blur_passes = 2` ou `blur_size = 8` dans `hyprlock.conf` pour préserver l'effet de verre dépoli Aurora tout en garantissant qu'aucun texte d'une fenêtre résiduelle ne soit déchiffrable.

### 4.4 Patch PAM Anti-Deadlock (`hyprlock-pam-deadlock.patch`)
- **Problématique d'origine dans Hyprlock amont** :
  La classe `CPam` instancie un thread de conversation PAM. Lors d'un arrêt prématuré (signal SIGUSR1, délai expiré, ou `kill` ordonné par `lock.sh`), le thread de conversation restait bloqué dans `m_sConversationState.inputSubmittedCondition.wait()` ou à l'intérieur de `pam_authenticate()`. Le destructeur `~CPam()` était vide, entraînant un blocage complet (deadlock) ou des processus d'authentification zombies.
- **Correctifs apportés par le patch** :
  1. *Variables atomiques* : Passage de `m_fadeOutOrTerminate` et `m_bTerminate` en `std::atomic_bool` dans `CHyprlock`.
  2. *Drapeau d'interruption* : Ajout de `std::atomic_bool terminateRequested` dans `ConversationState`.
  3. *Sortie de conversation sécurisée* : Ajout de la lambda `abortConversation()` qui libère la mémoire allouée (`pamReply`) et retourne immédiatement `PAM_CONV_ERR` si une interruption est requise.
  4. *Destruction déterministe* : Implémentation de `CPam::~CPam() { terminate(); }` réveillant la condition variable et rejoignant le thread (`m_thread.join()`).
- **Verdict d'architecture** : Le patch est rigoureusement conforme aux exigences de robustesse multithread C++20 et indispensable à la stabilité de la chaîne.

---

## 5. Synthèse des Anomalies & Spécifications pour le Programmeur

| Réf. | Composant | Gravité | Description du Risque | Action Spécifiée pour le Programmeur |
| :--- | :--- | :--- | :--- | :--- |
| **A-01** | `workspace-autocompact.py` | Moyenne | Timeout absent sur socket commande `hypr_cmd()` | Ajouter `s.settimeout(1.0)` avant `s.connect()`. |
| **A-02** | `workspace-autocompact.py` | Moyenne | Boucle d'écho sur `movewindow` lors du compactage | Drainer le tampon du socket à la fin de `compact_workspaces()`. |
| **A-03** | `workspace-autocompact.py` | Faible | Perte d'événements pendant l'exécution | Remplacer `is_compacting` par un mécanisme de réarmement en différé. |
| **A-04** | `workspace-autocompact.py` | Élevée | Reconnexion bloquée sur socket mort après crash Hyprland | Forcer le recalcul du chemin socket le plus récent si échec répété. |
| **A-05** | `workspace-autocompact.py` | Moyenne | Régression compactage si écran secondaire absent | Préserver les tranches d'espaces des écrans non connectés. |
| **A-06** | `hyprlock_state.py` | Élevée | Blocage infini du watcher sur socket bloquant | Implémenter `select.select()` avec timeout 0.5 s sur la boucle d'événements. |
| **A-07** | `hyprlock_state.py` | Élevée | Écran branché sous verrou abandonné sur espace 97 | Dans `restore_state()`, assigner un espace légitime aux écrans inconnus d'`orig`. |
| **A-08** | `hyprlock_state.py` | Moyenne | Absence de debounce sur `enforce_lock()` | Ajouter un debounce de 50 ms pour regrouper les événements IPC. |
| **A-09** | `lock.sh` | Moyenne | Hiding Waybar/SwayNC asynchrone laissant fuiter l'UI | Exécuter l'arrêt de Waybar et DND SwayNC de manière synchrone avant `hyprlock`. |
| **A-10** | `hypridle.conf` | Élevée | Écrans allumés indéfiniment sous verrou, pas de veille | Ajouter les paliers DPMS off (330 s) et Suspend (1800 s) + `dpms on`. |
| **A-11** | `hyprlock.conf` | Moyenne | Translucidité 0.50 sans flou : fuite visuelle si bug IPC | Ajouter un flou de sécurité (`blur_passes = 2`, `blur_size = 6`). |

---

## 6. Conclusion de l'Architecte

L'architecture actuelle présente d'excellentes fondations techniques (mutex singleton `flock`, isolation d'espaces virtuels 97/98/99, patch PAM anti-deadlock). Les vulnérabilités identifiées relèvent principalement de la gestion des états transitoires (timeouts réseau UNIX, drainage d'événements IPC, cohérence des paliers d'inactivité énergétique et réintégration d'écrans chauds).

Le passage de ces spécifications au Programmeur permettra de consolider l'intégralité de la chaîne sans rupture d'interface ni dépassement volumétrique.
