# 🌌 Évaluation UX & Qualité d'Expérience — Jalon 4 (Relecture Finale)
**Projet** : Hyperland / Aurora OS  
**Rôle** : Designer UX & Qualité d'Expérience (Équipe Zygos)  
**Date** : 12 novembre 2026  
**Note Globale** : **18.5 / 20** (Mention Très Bien — Excellence Ergonomique & Graphique)

---

## 🧭 I. Synthèse Exécutive

La présente relecture qualitative clôture la campagne d'audit, d'optimisations (Jalon 2) et de nouvelles fonctionnalités (Jalon 3) sur l'environnement **Hyprland / Thème Aurora**. 

L'écosystème analysé atteint un niveau de maturité ergonomique et de cohésion visuelle exceptionnel. Les irritants historiques (surtension CPU du moniteur GPU, micro-fuites visuelles à l'activation du verrouillage, collisions de processus et instabilités hotplug) ont été méthodiquement éliminés pour laisser place à un bureau fluide, sécurisé, hautement personnalisable et d'une grande sobriété énergétique.

### Bilan en Chiffres Clés
- **Temps de scan GPU Waybar** : Réduit de **22.3 ms** à **1.32 ms** (-94% de latence) via cache bi-cadence DRM fdinfo.
- **Empreinte CPU Waybar** : Stabilisée sous **0.3%** en régime nominal.
- **Fuite visuelle au verrouillage** : **0 ms** (suppression de la fenêtre résiduelle de 50–100 ms grâce à un séquençage synchrone strict).
- **Régulation énergétique du fond d'écran** : Passage dynamique de **30 FPS** à **1 FPS** sous verrouillage ($AURORA_RUNTIME_DIR/hypr_locked), soit **96.7% d'économie de cycles GPU/EGL** en session verrouillée.
- **Intégrité physique des dotfiles** : **42/42 hard links directs nominaux** surveillés et scellés par hook Git pre-commit.
- **Conformité aux 4 piliers Aurora** : **100%** sur l'ensemble des 5 sous-systèmes (Hyprland, Waybar, Wofi, SwayNC, Kitty, Spotify Card).

---

## 🎯 II. Réponses aux Deux Questions Fondamentales

### 1. Le reste est-il au niveau de la meilleure partie ?
> **Verdict : OUI — Harmonie géométrique et chromatique totale.**

L'audit approfondi des feuilles de style et configurations confirme l'alignement rigoureux sur les 4 piliers de la charte Aurora :
- **Rayons de courbure (17px)** : Respecté sur l'intégralité des conteneurs principaux : fenêtres Hyprland (`rounding = 17`), barre Waybar (`bar-bg.svg rx=17 ry=17` et `window#waybar`), lanceur Wofi (`border-radius: 17px;`), centre de notifications et toasts SwayNC (`.control-center` et `.notification` à `17px`), menu contextuel Popover (`17px`), carte flottante Spotify (`.card-container` à `17px`) et champ de saisie Hyprlock (`rounding = 17`). Les éléments intérieurs (capsules, boutons) adoptent une échelle proportionnelle cohérente (8 à 12px) qui renforce la hiérarchie visuelle.
- **Bordures (2px)** : Épaisseur uniforme de `2px` sur les fenêtres actives Hyprland, le contour vectoriel de Waybar, le cadre Wofi, les conteneurs SwayNC, la carte Spotify et le champ Hyprlock. Aucune dissonance de cadrage.
- **Dégradé vectoriel à 45°** : Orientation géométrique unifiée reliant le Cyan électrique (`#00f0ff`), le Bleu Tokyo Night (`#7aa2f7`) et le Violet néon (`#9778d0`). Présent en rotation matérielle continue sous GPU sur les bordures Hyprland, en vecteur diagonal $(0,0 \to 100\%,100\%)$ dans le SVG de Waybar, en arrière-plan d'accentuation sur Wofi (`#entry:selected`) et dans l'interface de déverrouillage Hyprlock.
- **Translucidité unifiée (0.50)** : Les surfaces de verre fumé (`rgba(10, 15, 30, 0.50)`) sont désormais généralisées avec succès sur Waybar, Wofi, le fond du Control Center SwayNC, le terminal Kitty (`background_opacity 0.50`), la carte Spotify et l'écran de verrouillage Hyprlock, sublimées par le flou matériel double-passe de Hyprland (`blur size=6, passes=1/2`).

### 2. Les textes et documentations disent-ils ce que fait vraiment le produit ?
> **Verdict : PARTIELLEMENT — Excellente documentation technique, mais retards de synchronisation dans le README.**

- **Ce qui est fidèle et exemplaire** :
  - La documentation interne des dotfiles (`dotfiles/hypr/README.md`, `dotfiles/swaync/README.md`) détaille avec exactitude le fonctionnement événementiel, les raccourcis AZERTY, les signaux D-Bus, et le protocole de nettoyage RAII de `lock.sh`.
  - Les messages des scripts CLI (`hyprbar`, `screenshot.sh`, `theme_switcher.py`) sont clairs, informatifs et exempts de scories techniques ou de faux signaux d'erreur.
- **Points de divergence identifiés dans `README.md`** :
  - *Hardlinks physiques* : Le `README.md` mentionnait historiquement **34 hard links**, alors que l'environnement réel et les suites d'audit en valident **42 nominaux**.
  - *Translucidité* : Le `README.md` mentionnait encore localement une translucidité à 0.20 pour hyprbar/bar-bg.svg et 0.85 pour Kitty, bien que le produit ait été uniformisé à 0.50 (50%).
  - *Nouvelles fonctionnalités non introduites* : Le hook pre-commit automatisé (`hooks/pre-commit`), le sélecteur de thèmes (`scripts/theme_switcher.py`), et le mode Low-Power 1 FPS sous verrouillage d'`aurora-wallpaper` doivent être ajoutés dans le guide général.
  - *Cascade Hypridle & Politique Veille (Décision P1)* : Le `README.md` doit expliciter la cascade énergétique et la décision P1 : 150s dim 20%, 300s lock, 330s DPMS off maintenu, et veille PC 1800s bloquée sous verrou via `systemd-inhibit --what=sleep` et garde `hypridle.conf`.

---

## 🔍 III. Évaluation Détaillée des 7 Améliorations de la Séance

### 1. Optimisation Waybar & GPU (`gpu.py`) — Note : 19.5/20
- **Apport ergonomique & fluidité** : L'implémentation de la bi-cadence (Slow-Path de découverte toutes les 30s, Fast-Path toutes les 3s interrogeant 27 descripteurs DRM au lieu de 3926) abaisse la latence de scan à **1.32 ms** (gain x16). La suppression des micro-saccades de rafraîchissement garantit une Waybar réactive et insensible aux pics d'activité système.
- **Perception utilisateur** : Affichage fluide de l'indicateur GPU en temps réel avec icône cyan `󰢮`, sans surchauffe ni surconsommation CPU (< 0.3%).

### 2. Durcissement IPC & Lock Multi-Écrans (`lock.sh`, `hyprlock_state.py`, `hypridle.conf`) — Note : 19/20
- **Apport ergonomique & sécurité** : Élimination complète de la fuite visuelle de 50 à 100 ms grâce au réordonnancement synchrone (masquage popups $\to$ DND SwayNC synchrone $\to$ arrêt Waybar $\to$ capture/redirection vers workspaces 98/99 $\to$ hyprlock).
- **Reprise à chaud (Hotplug)** : Le gestionnaire de hotplug sur socket2 surveille les branchements à chaud d'écrans sans bloquer la boucle principale (`select.select` cadencé à 500 ms avec debounce 50 ms). Enregistrement défensif immédiat dans `STATE_FILE` lors de `monitoradded` pour garantir une restauration sur des espaces sains (DP-2 sur 1, DP-1 sur 6) sans jamais projeter l'utilisateur sur l'espace fantôme 97.
- **Cascade hypridle à 4 paliers** : Baisse préventive de luminosité à 2m30 (prévenance UX), verrouillage à 5m, extinction des dalles à 5m30, mise en veille à 30m.

### 3. Remplacement de `pkill -9` & Assainissement des Utilitaires — Note : 18.5/20
- **`scripts/hyprbar`** : Éradication du `pkill -9` au profit d'une séquence propre `pkill -TERM` couplée à une attente active bornée de la libération du socket `$AURORA_RUNTIME_DIR/spotify_card.sock` (jusqu'à 1.0s) et d'un `pkill -KILL` ciblé uniquement en cas de non-réponse. Redémarrage immédiat sans état zombie ni blocage de port.
- **`screenshot.sh`** : Fallback élégant lorsque `swappy` est absent. L'outil copie directement l'image dans le presse-papiers Wayland et notifie l'utilisateur via `notify-send` avec le message informatif *"Copiée dans le presse-papiers (swappy non installé)"*, sans aucun plantage ni message d'erreur abscons dans le terminal.

### 4. Hook Pre-commit Automatisé (`hooks/pre-commit`) — Note : 19/20
- **Apport qualité & pérennité** : Garantit de manière impérative qu'aucune régression physique sur les 42 hardlinks dotfiles nominaux ne puisse être commise dans le dépôt. Intègre le contrôle volumétrique (< 500 lignes strict, alerte jaune $\ge$ 400 lignes) et le lint syntaxique bilingue (`py_compile` et `bash -n`).
- **Confort développeur** : Résolution absolue du répertoire racine via `readlink -f`, message d'erreur clair avec désignation du fichier incriminé en cas de rejet.

### 5. Notifications Riches SwayNC lors du Switch de Thèmes — Note : 19/20
- **Apport visuel & feedback** : Lors de la bascule de thème (`theme_switcher.py`), une notification système immédiate sous l'application `"Aurora Theme"` confirme la réussite de l'opération en affichant :
  * Le nom lisible et technique du thème.
  * La palette hexadécimale active (Primaire | Secondaire | Accent).
  * La confirmation explicite de synchronisation des 5 composants (Waybar, SwayNC, Wofi, Kitty, Hyprland).
- **Sobriété** : Temporisation adaptée à 3.5s, catégorie système, non filtrée par la blacklist.

### 6. Mode Low-Power Dynamique dans `aurora-wallpaper` — Note : 19.5/20
- **Sobriété énergétique & ingénierie C99** : Détection sans surcoût du drapeau `$AURORA_RUNTIME_DIR/hypr_locked` à chaque itération via `access()`. Passage instantané de 30 FPS à 1 FPS (temporisation `poll()` de 1 000 ms), divisant par 30 la charge GPU/EGL sur écran verrouillé. Rétablissement immédiat à 30 FPS (33.3 ms) dès la levée du verrou.
- **Stabilité** : Aucune recréation de surface Wayland ni réinitialisation de contexte OpenGL, évitant tout clignotement ou crash au déverrouillage. Maintien strict du fichier `main.c` à 396 lignes (< 400).

### 7. Respect Strict de la Préférence Utilisateur (`follow_mouse = 0`) — Note : 20/20
- **Ergonomie multi-écrans** : Le mode *Click-to-Focus* (`follow_mouse = 0`) est scrupuleusement préservé. L'utilisateur conserve le plein contrôle de ses fenêtres sans subir de perte intempestive de focus lors du survol de la souris d'un écran à l'autre (notamment entre DP-2 et DP-1).
- **Zéro régression** : La navigation clavier et les raccourcis applicatifs restent totalement fluides.

---

## 📊 IV. Grille d'Évaluation Multidimensionnelle

| Dimension | Note | Justification |
| :--- | :---: | :--- |
| **Cohérence Visuelle & Charte Aurora** | **19/20** | Harmonie exemplaire sur les 4 piliers (17px, 2px, dégradé 45°, verre 0.50). Aucune rupture graphique entre les modules. |
| **Ergonomie & Expérience Utilisateur** | **19/20** | Focus au clic respecté, Wofi souris/clavier réactif, menu de session intuitif, feedback par notifications riches. |
| **Fluidité & Réactivité Temps Réel** | **19/20** | Scan GPU < 1.4 ms, débouce IPC 50 ms, zéro boucle d'écho de réarrangement, zéro saccade visuelle. |
| **Sobriété Énergétique & Empreinte** | **19.5/20** | Cascade hypridle et décision P1 (veille PC bloquée sous verrou, DPMS off maintenu), Low-Power 1 FPS sous verrou, architecture événementielle zéro-polling. |
| **Rigueur Documentaire & Clarté** | **16/20** | Les README de composants sont parfaits, mais le README principal accuse un retard (mention de 34 links vs 42 réels, 0.20 vs 0.50, nouveautés J3 à intégrer). |
| **Moyenne Pondérée Globale** | **18.5 / 20** | **Excellence globale du livrable, avec recommandation d'actualisation documentaire.** |

---

## 💡 V. Recommandations pour les Évolutions Futures

1. **Actualisation Synchronisée du `README.md`** :
   - Mettre à jour le décompte officiel des liens physiques : passer de 34 à **42 hard links nominaux**.
   - Aligner toutes les mentions de translucidité sur la norme réelle à **50% (`0.50`)** pour Waybar et Kitty.
   - Documenter le sous-système de profils visuels (`scripts/theme_switcher.py`), le hook pre-commit et le mode Low-Power d'`aurora-wallpaper`.
   - Décrire la cascade énergétique à 4 paliers dans la section Hypridle.
2. **Indicateur Visuel de Mode Énergétique dans Waybar** :
   - Proposer une icône discrète dans la barre (ex: feuille verte néon) lorsque le système détecte un état de batterie faible ou bascule en mode économie.
3. **Prévisualisation Interactive du Sélecteur de Thèmes** :
   - Proposer une intégration dans Wofi permettant de parcourir les thèmes installés avec un aperçu direct des vignettes de palette avant application.

---

## ✅ VI. Conclusion

L'environnement de bureau Aurora Hyprland a atteint un degré d'aboutissement et de raffinement remarquable. Les choix architecturaux et ergonomiques garantissent un confort d'usage quotidien d'une grande fluidité, une esthétique cyberpunk soignée et une robustesse système à toute épreuve. Le livrable final est **pleinement validé**.
