# Centre de Notifications SwayNC (`dotfiles/swaync/`) 🔔

Configuration et thématisation du centre de notifications **SwayNC** (*Sway Notification Center*) sous Wayland / Hyprland, harmonisé avec la charte graphique **Aurora** et intégré au protocole de confidentialité de session.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/swaync/
├── config.json             # Structure des widgets (titre, DND, mpris, liste), géométrie (largeur 420px, marges)
├── style.css               # Feuille de style GTK3 (glassmorphism rgba(10, 15, 30, 0.80), coins 17px, bordures cyan 2px)
├── swaync-blacklist.patch  # Patch natif Vala pour menu contextuel au clic droit (Blacklist / Fermer)
├── scripts/
│   └── blacklist-app.py   # Helper Python pour insertion in-place dans notification-visibility (respect hardlinks)
└── README.md               # Documentation technique du centre de notifications
```

---

## 🖱️ Navigation Souris & Blacklist d'Applications (Patch Clic Droit)

Par défaut sous SwayNC, un clic droit ferme la notification sans action supplémentaire. Le patch natif [`swaync-blacklist.patch`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/swaync/swaync-blacklist.patch) enrichit l'ergonomie :
- **Menu Contextuel Popover (`button-press-event` bouton 3)** : Un clic droit sur n'importe quelle notification (popup ou panneau latéral) ouvre une modale Popover Aurora ciblée sur les coordonnées du pointeur.
- **Action « 🚫 Blacklister [App] »** : Appelle le script [`scripts/blacklist-app.py`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/swaync/scripts/blacklist-app.py) qui injecte de manière atomique une règle `state: "ignored"` dans `~/.config/swaync/config.json` en écriture *in-place* (stricte préservation des 34/34 hardlinks sans rupture d'inode).
- **Prise d'effet instantanée** : Déclenche immédiatement `swaync-client -R` et confirme le blocage par une notification système.
- **Action « ✕ Fermer »** : Ferme simplement la notification.
- **Neutralisation du Timeout** : Dès l'ouverture du menu contextuel, le timer d'expiration de la notification est suspendu pour éviter toute disparition pendant la sélection.

---

## 🎨 Spécifications Visuelles (GTK3 CSS & Charte Aurora)

- **Coins arrondis** : **`17px`** obligatoires sur le panneau de contrôle (`.control-center`), les conteneurs de notifications individuelles (`.notification`) et les boutons d'action.
- **Bordures & Lueur** : **`2px`** cyan néon (`#00f0ff` / `rgba(0, 240, 255, 0.60)`) avec ombres portées douces sur le panneau actif.
- **Glassmorphism** : Arrière-plan sombre translucide `rgba(10, 15, 30, 0.80)` enrichi par le flou de composition matériel Hyprland (`layerrule = blur, swaync-control-center` et `layerrule = blur, swaync-notification-window`).
- **Niveaux d'Urgence** :
  - *Faible / Normal* : Accent cyan `#00f0ff` et fond sombre uniforme.
  - *Critique* : Bordure et bouton d'action rouge/rose néon (`#f43f5e` / `#f87171`) pour une identification immédiate.
- **Interrupteur Ne Pas Déranger (DND)** : Bouton à bascule stylisé avec pastille lumineuse et transitions fluides.

---

## 🔒 Confidentialité & Masquage sous Verrouillage (`lock.sh`)

Pour éviter toute fuite d'informations sensibles (messages privés, alertes, codes 2FA) sur l'écran de verrouillage ou lors du réveil DPMS des moniteurs :

1. **Activation Automatique du Mode Ne Pas Déranger** :
   - À l'entrée dans le script [`lock.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/lock.sh), l'état DND préalable est mémorisé (`PREV_DND=$(swaync-client -D)`).
   - Fermeture immédiate de tout panneau ouvert (`swaync-client -cp`).
   - Activation stricte du mode DND (`swaync-client -dn`).
2. **Suppression Totale des Couches Wayland Parasites** :
   - Pendant le verrouillage, aucun toast de notification n'apparaît à l'écran (niveau de couche `swaync-notification-window = 0`).
   - Les notifications entrantes continuent d'être réceptionnées via D-Bus (`org.freedesktop.Notifications`) et sont archivées silencieusement dans l'historique sans émettre de popups.
3. **Restauration de Session Propre (RAII)** :
   - Lors du déverrouillage dans la routine `cleanup()`, si le mode DND n'était pas actif avant le verrouillage, il est immédiatement réactivé (`swaync-client -df`).

---

## ⌨️ Raccourcis & Commandes CLI

### Raccourci Clavier Hyprland
- <kbd>SUPER</kbd> + <kbd>N</kbd> : Ouvrir / Fermer le volet du centre de notifications (`swaync-client -t -sw`)

### Commandes Utilitaires (`swaync-client`)
```bash
# Ouvrir / Fermer le panneau latéral
swaync-client -t -sw

# Basculer le mode Ne Pas Déranger (DND)
swaync-client -d

# Effacer toutes les notifications
swaync-client -C

# Recharger la configuration JSON et la feuille de style CSS à chaud
swaync-client -R && swaync-client -rs

# Consulter l'état courant
swaync-client -c   # Nombre de notifications
swaync-client -D   # État DND (true/false)
```
