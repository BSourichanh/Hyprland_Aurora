# Lanceur d'Applications Wofi (`dotfiles/wofi/`) 🚀

Configuration et thématisation du lanceur d'applications **Wofi** sous Wayland / Hyprland, harmonisé avec la charte graphique **Aurora** et piloté par le gestionnaire d'événements `wofi-toggle.sh`.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/wofi/
├── config                  # Paramètres d'affichage, prompt, single_click et filtrage
├── style.css               # Style GTK3 principal (dégradé 135°, coins 17px, lueur cyan, survol néon)
├── power-menu.css          # Style dédié compact pour la modale d'alimentation & session
└── wofi-hover-select.patch # Patch C natif GTK3 pour sélection active au survol de la souris
```

---

## 🎨 Spécifications Visuelles (GTK3 CSS)

- **Coins arrondis** : **`17px`** sur la fenêtre principale et le champ de recherche.
- **Bordure en dégradé continu** : Angle 135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`) avec épaisseur de **2px**.
- **Arrière-plan** : Fond sombre translucide `rgba(10, 15, 30, 0.88)` complété par le flou matériel Hyprland.
- **Champ de saisie (`#input`)** : Curseur cyan, texte contrasté, bordure dégradée fine et ombre portée néon (`box-shadow: 0 0 12px rgba(0, 240, 255, 0.35)`).
- **Éléments sélectionnés (`#entry:selected`)** : Surlignage en dégradé cyan / violet avec texte sombre contrasté.

---

## 🖱️ Navigation Ergonomique Souris (Patch Hover-Select)

Par défaut, Wofi est un lanceur exclusivement centré sur le clavier (seules les flèches modifient la sélection active). Le patch natif [`wofi-hover-select.patch`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/wofi/wofi-hover-select.patch) ajoute une navigation hybride intuitive :
- **Sélection dynamique au survol (`motion-notify-event`)** : Déplacer le curseur sur n'importe quelle entrée déplace immédiatement la capsule de sélection Aurora (`#entry:selected`), comme avec les flèches du clavier.
- **Lancement en un seul clic (`single_click=true`)** : Un simple clic gauche exécute directement l'application sélectionnée.
- **Saisie continue sans perte de focus** : Le champ `#input` conserve en permanence le focus clavier pour chercher et taper sans interruption.

---

## ⚡ Feuille de Style Dédiée : Menu d'Alimentation (`power-menu.css`)

Pour le menu de session (`Super + S` / `power-menu.sh`), une feuille de style dédiée supprime la zone de recherche et présente les actions sous forme de capsules tactiles :
- **Écrasement d'espace `#input`** : Annule l'allocation d'espace résiduel par GTK (`min-height: 0`, échelle d'icône 0) pour éliminer tout décalage supérieur.
- **Capsules de verre (`#entry`)** : Fond translucide `rgba(255, 255, 255, 0.04)`, bordure fine Tokyo Night `1px solid rgba(122, 162, 247, 0.16)` et arrondi 12px.
- **Survol & Sélection** : Surbrillance cyan au survol et plein dégradé néon Aurora 45° (`#00f0ff` ➔ `#7aa2f7`) sur l'élément sélectionné avec typographie sombre contrastée `#090727`.

---

## ⚙️ Mécanisme de Fermeture au Clic Extérieur (`wofi-toggle.sh`)

Sous Wayland / wlroots, Wofi ne dispose pas nativement d'un événement `unfocus` fiable pour se refermer lors d'un clic en dehors de sa fenêtre.

Le script [`wofi-toggle.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/wofi-toggle.sh) implémente une solution événementielle :
1. **Backdrop Transparent Plein Écran** : Déploie une surface Wayland invisible couvrant l'ensemble du moniteur en arrière-plan immédiat de Wofi.
2. **Synchronisation Noyau (`wait -n`)** : Utilise l'appel système `wait -n` pour attendre simultanément la fin de Wofi ou un clic sur le backdrop. **Zéro boucle active (`while sleep`) et 0% de charge CPU**.
3. **Nettoyage Automatique** : Dès qu'une action survient (clic extérieur, validation ou touche Échap), le gestionnaire de signaux termine instantanément les deux processus.

---

## ⌨️ Raccourcis & Utilisation

- Ouvrir / Fermer le lanceur d'applications : <kbd>SUPER</kbd> + <kbd>R</kbd>
- Ouvrir / Fermer le menu d'alimentation : <kbd>SUPER</kbd> + <kbd>S</kbd>
- Lancement direct en ligne de commande :
  ```bash
  ~/.config/hypr/scripts/wofi-toggle.sh
  ~/.config/hypr/scripts/power-menu.sh
  ```
