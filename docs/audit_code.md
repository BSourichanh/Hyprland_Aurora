# Rapport d'Audit Technique Approfondi — Python, Scripts Système & Moteur Natif C99

**Auteur** : Architecte (Équipe Zygos)  
**Projet** : Hyperland (`/home/user/Documents/antigravity/hyprland_project`)  
**Tâche** : T2 — Audit approfondi du code Python et du moteur natif C99  
**Statut** : Validé  

---

## 1. Périmètre & Méthodologie

L'audit couvre l'ensemble des modules logiciels du bureau Aurora Hyprland :
- Modules Python de thématisation dynamique : `scripts/theme_switcher.py`, `scripts/theme_models.py`, `scripts/theme_templates.py`.
- Serveur MCP et intégrations : `scripts/aurora_mcp_server.py`, `scripts/aurora_mcp/system_tools.py`, `scripts/aurora_mcp/media_tools.py`.
- Scripts système et démons IPC : `scripts/hyprbar`, `scripts/wallpaper_tool.py`, `scripts/wallpaper_status.py`, `setup.sh`.
- Moteur graphique natif C99 Wayland : `src/aurora_wallpaper/main.c`, `gl_utils.c`, `gl_utils.h`, `shader.h`, `Makefile`.
- Conformité volumétrique globale (plafond strict < 500 lignes, seuil d'alerte $\ge 400$ lignes).

---

## 2. Volumétrie & Règles de Modularité (< 500 Lignes)

### 2.1 Synthèse de l'inspection volumétrique
Chaque fichier source et script du projet a été mesuré (`wc -l`) :
- **Infraction absolue (> 500 lignes)** : **0 fichier**. Aucun fichier de code interne ne dépasse la limite stricte de 500 lignes. (Les fichiers tiers ou générés comme `stb_image.h` [7988 l.], `xdg-shell-client-protocol.h` [2392 l.], `wlr-layer-shell-unstable-v1-client-protocol.h` [563 l.] et l'extension externe `nautilus_open_any_terminal.py` [644 l.] sont exclus du périmètre de refactorisation interne).
- **Seuil d'alerte ($\ge 400$ lignes)** :
  1. `setup.sh` : **428 lignes** (Alerte confirmée, nécessite modularisation).
  2. `scripts/wallpaper_tool.py` : **398 lignes** (Seuil critique, à 2 lignes de l'alerte).
  3. `src/aurora_wallpaper/main.c` : **396 lignes** (Seuil critique, à 4 lignes de l'alerte).

---

## 3. Audit Approfondi du Code Python & Scripts Système

### 3.1 Thématisation Dynamique (`theme_switcher.py`, `theme_models.py`, `theme_templates.py`)

#### Faiblesse 1 : Écriture in-place non atomique et risque de corruption à 0 octet
- **Fichier** : `scripts/theme_switcher.py`, lignes 28–36 :
```python
def write_inplace(path: Path, content: str):
    """Overwrites file in-place to strictly preserve file inode and hardlinks."""
    orig_inode = path.stat().st_ino
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    new_inode = path.stat().st_ino
    if orig_inode != new_inode:
        raise RuntimeError(f"Rupture de hardlink sur {path} (inode {orig_inode} != {new_inode})")
```
- **Diagnostic** : Le mode `"w"` effectue un `truncate(0)` immédiat dès l'ouverture du descripteur. En cas de coupure brutale, d'exception mémoire ou d'espace disque saturé pendant `f.write()`, le fichier de configuration (Waybar, SwayNC, Wofi, Kitty) reste vidé à 0 octet, corrompant la session Wayland. De plus, `path.stat()` échoue avec `FileNotFoundError` si le fichier n'existe pas encore.
- **Correction requise** : Utiliser le mode `"r+"` avec écriture préalable puis tronquature : `open(path, "r+")` -> `seek(0)` -> `write(content)` -> `truncate()`, ou valider l'intégrité avant ouverture.

#### Faiblesse 2 : Expressions régulières fragiles et destructives
- **Fichier** : `scripts/theme_switcher.py`, lignes 70–71 :
```python
new_text = re.sub(r"@define-color cc-bg.*?(?=\n\n\*)", def_colors, text, flags=re.DOTALL)
write_inplace(path, new_text)
```
- **Fichier** : `scripts/theme_switcher.py`, lignes 124–125 :
```python
new_text = re.sub(r"# Colors.*", colors_block, text, flags=re.DOTALL)
write_inplace(path, new_text)
```
- **Diagnostic** :
  1. Dans `update_swaync_css`, la regex suppose la présence exacte d'un saut de ligne double avant `*` (`(?=\n\n\*)`). Si un utilisateur commente ou reformate la feuille de style, la substitution échoue silencieusement et réécrit le texte inchangé.
  2. Dans `update_kitty_conf`, `r"# Colors.*"` avec `re.DOTALL` absorbe l'intégralité du fichier jusqu'à la fin. Toute directive utilisateur ajoutée après le bloc de couleurs est écrasée.
- **Correction requise** : Délimiter les blocs injectés par des balises sentinelles explicites : `/* AURORA_THEME_START */` ... `/* AURORA_THEME_END */`.

#### Faiblesse 3 : Absence de validation des codes hexadécimaux et risque de ValueError
- **Fichier** : `scripts/theme_templates.py`, lignes 15–20 :
```python
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.lstrip("#")
    if len(h) >= 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0, 240, 255
```
- **Diagnostic** : Aucune validation de conformité hexadécimale (`^[0-9a-fA-F]{6}$`). Une chaîne comme `#invalid` ou `#zzzzzz` lève une exception `ValueError` non interceptée lors de la génération des CSS.

---

### 3.2 Serveur FastMCP & Outils Modulaires (`system_tools.py`, `media_tools.py`, `aurora_mcp_server.py`)

#### Anomalie Majeure 1 : Bug critique d'évaluation dans `reload_all()`
- **Fichier** : `scripts/aurora_mcp/system_tools.py`, lignes 59–64 et 227–232 :
```python
# _check_hardlinks_dict() retourne :
return {
    "total_checked": checked,
    "missing": missing,
    "mismatches": mismatches,
    "all_ok": len(mismatches) == 0 and len(missing) == 0
}
...
# Dans reload_all() :
results["hardlinks"] = _check_hardlinks_dict()
return {
    "ok": all(r.get("ok", False) for r in results.values()),
    "actions": results
}
```
- **Preuve & Impact** : `_check_hardlinks_dict()` fournit la clé `"all_ok"`, mais `reload_all()` interroge `r.get("ok", False)`. Pour `results["hardlinks"]`, l'appel retourne systématiquement `False`. **Conséquence : `reload_all()` renvoie toujours `ok: False`, même lorsque toutes les opérations et audits réussissent à 100%.**
- **Correction requise** : Normaliser la clé avec `"ok": len(mismatches) == 0 and len(missing) == 0` dans `_check_hardlinks_dict()`.

#### Anomalie 2 : Faux positif d'état du démon Spotify Floating Card
- **Fichier** : `scripts/aurora_mcp_server.py`, ligne 139 :
```python
card_daemon_running = Path("/tmp/spotify_card.lock").exists()
```
- **Diagnostic** : Le fichier `/tmp/spotify_card.lock` est créé lors du premier verrou `flock`. Lorsqu'un processus se termine (ou est tué via `pkill -9`), le descripteur `flock` est libéré par le noyau, mais le fichier reste présent sur le système de fichiers `/tmp`. `card_daemon_running` rapporte donc `True` indéfiniment.
- **Correction requise** : Tester la présence du processus actif (`pgrep -f "spotify-card.py"`) ou tenter une acquisition non bloquante `fcntl.flock(LOCK_EX | LOCK_NB)`.

#### Anomalie 3 : Déconnexion partielle et retour non inspecté dans SwayNC reload
- **Fichier** : `scripts/aurora_mcp/system_tools.py`, lignes 220–222 :
```python
res_swaync = subprocess.run(["swaync-client", "-R"], capture_output=True, text=True, timeout=3)
subprocess.run(["swaync-client", "-rs"], capture_output=True, text=True, timeout=3)
results["swaync"] = {"ok": res_swaync.returncode == 0}
```
- **Diagnostic** : Le second appel (`-rs` pour recharger les feuilles de style CSS) n'a ni son code retour vérifié ni consigné dans `results["swaync"]`.

---

### 3.3 Scripts Système & Démons IPC (`hyprbar`, `wallpaper_tool.py`, `setup.sh`)

#### Faiblesse 1 : Fausse détection de processus zombie et course critique au démarrage
- **Fichier** : `scripts/wallpaper_tool.py`, lignes 201–215 :
```python
# Purge proactive de tout processus fantôme sans calque Wayland actif
active_pids = set(active_layers.values())
zombies = [pid for pid in running if pid not in active_pids]
if zombies:
    terminate_procs(zombies, timeout=0.2)
    running = get_running_wallpaper_procs()
```
- **Diagnostic** : Le micro-moteur `aurora-wallpaper` met entre 50 et 150 ms à initialiser le contexte EGL, compiler les shaders et s'enregistrer auprès de `wlr_layer_shell`. Pendant cette fenêtre, `hyprctl layers` ne liste pas encore son PID. Si `ensure_wallpapers()` est appelé de manière rapprochée (par exemple par deux événements IPC consécutifs), le processus légitime en cours d'initialisation est considéré à tort comme "zombie" et abattu via SIGTERM/SIGKILL.
- **Correction requise** : Introduire une période de grâce (ex: vérifier l'âge du processus via `/proc/<pid>/stat` ou attendre 250 ms avant de classifier un PID sans calque comme zombie).

#### Faiblesse 2 : Signaux brutaux `pkill -9` dans `hyprbar`
- **Fichier** : `scripts/hyprbar`, lignes 20–24 et 28–32 :
```bash
killall waybar 2>/dev/null
pkill -9 -f "spotify-card.py" 2>/dev/null
pkill -f "spotify.py" 2>/dev/null
pkill -f "gpu.py" 2>/dev/null
```
- **Diagnostic** : L'utilisation directe de `pkill -9` interdit toute libération des sockets UNIX (`/tmp/spotify_card.sock`) et des verrous GTK. `pkill` doit d'abord émettre `SIGTERM`, attendre 100 ms, puis recourir à `SIGKILL` en cas de non-réponse.

#### Faiblesse 3 : Volumétrie et antipatterns d'installation dans `setup.sh`
- **Fichier** : `setup.sh` (428 lignes).
- **Diagnostics** :
  1. *Dépassement de seuil* : 428 lignes (doit être découpé sous 400 lignes).
  2. *Antipattern `deploy_tripartite`* (lignes 30–53) : Copie directe sous `/usr/bin/` et `/usr/local/bin` sans passer par un gestionnaire de paquets (`dpkg`/`pacman`), risquant d'altérer la base du système hôte.
  3. *Dépendance cachée `uv`* (ligne 378) : Le script génère un binaire appelant `uv run`, or `uv` ne figure pas dans `SYSTEM_PKGS`.

---

## 4. Audit du Moteur Natif C99 (`src/aurora_wallpaper/`)

### 4.1 Protocole Wayland Layer-Shell & Inutilité de XDG-Shell
- **Fichier** : `src/aurora_wallpaper/main.c`, lignes 128–146 :
```c
out->wl_surface = wl_compositor_create_surface(app.compositor);
out->layer_surface = zwlr_layer_shell_v1_get_layer_surface(
    app.layer_shell,
    out->wl_surface,
    out->wl_output,
    ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM,
    "aurora-wallpaper"
);
```
- **Analyse** : Le moteur implémente correctement le protocole `zwlr_layer_shell_v1` en couche `ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM` avec ancrage aux 4 bords et zone exclusive de `-1` (fond d'écran sous toutes les fenêtres).
- **Constat XDG-Shell** : `xdg-shell-protocol.c` est compilé dans `Makefile` (ligne 5) uniquement parce que `wlr-layer-shell-unstable-v1-protocol.c` fait référence à `xdg_popup_interface`. Aucun objet XDG-shell (`xdg_wm_base`, `xdg_surface`, `xdg_toplevel`) n'est utilisé dans le moteur.

### 4.2 Boucle d'Événements & Polling Wayland
- **Fichier** : `src/aurora_wallpaper/main.c`, lignes 344–366 :
```c
struct pollfd pfd = { wl_display_get_fd(app.display), POLLIN, 0 };
poll(&pfd, 1, 0);

if (pfd.revents & POLLIN) {
    if (wl_display_read_events(app.display) != 0) {
        break;
    }
} else {
    wl_display_cancel_read(app.display);
}
...
render_frame();
wl_display_flush(app.display);

uint64_t elapsed_us = (get_time_ms() - t0) * 1000;
if (elapsed_us < frame_duration_us) {
    usleep(frame_duration_us - elapsed_us);
}
```
- **Faiblesses Techniques** :
  1. **Sommeil aveugle (`usleep`)** : Le `poll` est exécuté avec un timeout de 0 ms, puis le thread s'endort via `usleep` pendant près de 33 ms. Pendant cet intervalle, le processus est complètement sourd aux événements du compositeur (reconfiguration d'écran, unplug, ping). Une architecture réactive doit calculer le temps restant et le passer directement en argument de `poll(&pfd, 1, timeout_ms)`.
  2. **Non-gestion de `POLLHUP` / `POLLERR`** : Le code ne vérifie que `pfd.revents & POLLIN`. Si le serveur Wayland ferme la connexion, `POLLHUP` est émis sans `POLLIN`, entraînant un appel à `wl_display_cancel_read` puis une tentative d'écriture déclenchant une mort par signal.
  3. **Absence d'ignorance de `SIGPIPE`** : En cas de coupure du compositeur, `wl_display_flush()` provoque l'envoi d'un signal `SIGPIPE` non intercepté, terminant le processus brutalement sans passer par le bloc de nettoyage (`Arrêt propre du moteur Aurora...`).

### 4.3 Cycle de Vie Multi-Écrans & Hotplug
- **Fichier** : `src/aurora_wallpaper/main.c`, lignes 111–118 et 172–191 :
```c
static void layer_surface_closed(void *data, struct zwlr_layer_surface_v1 *layer_surface) {
    (void)layer_surface;
    struct Output *out = data;
    if (out) {
        printf("ℹ Surface d'affichage fermée [id=%u]\n", out->id);
        destroy_output_surface(out);
    }
}
```
- **Diagnostic** : Lorsque le compositeur détruit la surface calque (`layer_surface_closed`), `destroy_output_surface(out)` libère les ressources graphiques EGL, mais la structure `struct Output` demeure présente dans la liste chaînée `app.outputs`. Si `registry_global_remove` ne suit pas immédiatement, ce nœud persiste comme surface morte.
- **Régularité de libération** : L'ordre de destruction dans `destroy_output_surface` (`eglDestroySurface` -> `wl_egl_window_destroy` -> `zwlr_layer_surface_v1_destroy` -> `wl_surface_destroy`) respecte rigoureusement la hiérarchie des couches EGL/Wayland.
- **Mutualisation FBO** : Le rendu dans le FBO partagé (1920x1080) exécuté une seule fois par trame puis blitté vers tous les écrans connectés est une réussite architecturale majeure garantissant une charge GPU minimale.

---

## 5. Matrice de Priorisation des Correctifs

| Réf | Module | Sévérité | Problème constaté | Recommandation |
| :--- | :--- | :--- | :--- | :--- |
| **B1** | `system_tools.py` | **Bloquant** | Clé `"all_ok"` vs `"ok"` : `reload_all()` renvoie toujours `False`. | Aligner la clé sur `"ok"` dans `_check_hardlinks_dict()`. |
| **B2** | `wallpaper_tool.py` | **Majeur** | Faux positif zombie : kill prématuré de `aurora-wallpaper` au démarrage. | Ajouter un délai de grâce de 250 ms avant classification zombie. |
| **B3** | `theme_switcher.py` | **Majeur** | `write_inplace` non atomique (mode `"w"`) et regex destructives (`kitty.conf`). | Utiliser `"r+"` avec `truncate()` et balises sentinelles explicites. |
| **B4** | `aurora_mcp_server.py` | **Moyen** | `/tmp/spotify_card.lock` testé par `exists()` (faux positif démon actif). | Tester le PID actif ou acquérir le verrou `flock`. |
| **B5** | `main.c` (C99) | **Moyen** | `usleep` aveugle de 33 ms et omission de `signal(SIGPIPE, SIG_IGN)`. | Intégrer le délai dans `poll(&pfd, 1, timeout)` et ignorer `SIGPIPE`. |
| **B6** | `setup.sh` | **Alerte** | 428 lignes (dépassement seuil 400 l.) et écriture hors paquet `/usr/bin`. | Scinder `setup.sh` en sous-scripts modulaires (`< 400` lignes). |

---

## 6. Conclusion Architecturale

L'architecture globale d'Aurora OS présente une excellente cohérence : les principes de mutualisation FBO en C99, de contrôle des inodes dotfiles et d'exposition FastMCP sont fondateurs. Les vulnérabilités identifiées relèvent d'ajustements de robustesse système et d'alignement de contrats d'interfaces (clés de dictionnaire, concurrence de démarrage, gestion fine des signaux UNIX). Ces correctifs sont confiés au Programmeur pour implémentation.
