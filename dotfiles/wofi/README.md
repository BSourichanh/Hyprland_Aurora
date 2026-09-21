# Lanceur d'Applications Wofi (`dotfiles/wofi/`) 🚀

Configuration et thématisation du lanceur d'applications **Wofi** sous Wayland / Hyprland, harmonisé avec la charte graphique *Hybrid Summer* et piloté par le gestionnaire d'événements `wofi-toggle.sh`.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/wofi/
├── config        # Paramètres d'affichage, dimensions (460x520), prompt et comportement de filtrage
└── style.css     # Style GTK3 (bordure continue en dégradé 135°, coins 17px, lueur cyan)
```

---

## 🎨 Spécifications Visuelles (GTK3 CSS)

- **Coins arrondis** : **`17px`** sur la fenêtre principale et le champ de recherche.
- **Bordure en dégradé continu** : Angle 135° (`#00f0ff` ➔ `#7aa2f7` ➔ `#9778d0`) avec épaisseur de **2px**.
- **Arrière-plan** : Fond sombre translucide `rgba(10, 15, 30, 0.88)` complété par le flou matériel Hyprland.
- **Champ de saisie (`#input`)** : Curseur cyan, texte contrasté, bordure dégradée fine et ombre portée néon (`box-shadow: 0 0 12px rgba(0, 240, 255, 0.35)`).
- **Éléments sélectionnés (`#entry:selected`)** : Surlignage en dégradé cyan / violet avec texte sombre contrasté.

---

## ⚙️ Mécanisme de Fermeture au Clic Extérieur (`wofi-toggle.sh`)

Sous Wayland / wlroots, Wofi ne dispose pas nativement d'un événement `unfocus` fiable pour se refermer lors d'un clic en dehors de sa fenêtre.

Le script [`wofi-toggle.sh`](file:///home/user/Documents/antigravity/hyprland_project/dotfiles/hypr/scripts/wofi-toggle.sh) implémente une solution événementielle :
1. **Backdrop Transparent Plein Écran** : Déploie une surface Wayland invisible couvrant l'ensemble du moniteur en arrière-plan immédiat de Wofi.
2. **Synchronisation Noyau (`wait -n`)** : Utilise l'appel système `wait -n` pour attendre simultanément la fin de Wofi ou un clic sur le backdrop. **Zéro boucle active (`while sleep`) et 0% de charge CPU**.
3. **Nettoyage Automatique** : Dès qu'une action survient (clic extérieur, validation ou touche Échap), le gestionnaire de signaux termine instantanément les deux processus.

---

## ⌨️ Raccourci & Utilisation

- Ouvrir / Fermer Wofi : <kbd>SUPER</kbd> + <kbd>R</kbd>
- Lancement direct en ligne de commande :
  ```bash
  ~/.config/hypr/scripts/wofi-toggle.sh
  ```
