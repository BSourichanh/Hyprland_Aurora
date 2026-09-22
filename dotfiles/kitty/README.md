# Terminal Kitty (`dotfiles/kitty/`) 🖥️

Configuration du terminal accéléré par GPU **Kitty** pour l'environnement Hyprland, aligné sur la palette *Aurora (Tokyo Night / Néon)* avec translucidité matérielle.

---

## 📁 Arborescence & Rôles des Fichiers

```
dotfiles/kitty/
└── kitty.conf    # Paramètres d'apparence, police, opacité, marges et palette de couleurs
```

---

## 🎨 Spécifications Visuelles & Intégration

- **Translucidité & Flou** : `background_opacity 0.85`. Combiné au flou de composition d'Hyprland, il offre un effet de verre dépoli lisible et performant.
- **Marges Internes (Padding)** : `window_padding_width 14`. Évite que le texte de la console n'entre en collision avec les coins arrondis à 17px de la fenêtre Hyprland.
- **Typographie** : Police à espacement fixe (`font_family monospace`), taille `11.5pt`.
- **Fermeture Silencieuse** : `confirm_os_window_close 0` pour une fermeture instantanée sans avertissement bloquant.

---

## 🎨 Palette de Couleurs (Tokyo Night / Neon)

| Rôle | Couleur | Valeur Hex |
| :--- | :--- | :--- |
| **Arrière-plan** | Noir profond bleuté | `#0f111a` |
| **Texte principal** | Blanc doux | `#c0caf5` |
| **Curseur & Cyan** | Cyan néon | `#7dcfff` |
| **Sélection & Bleu** | Bleu Tokyo Night | `#7aa2f7` |
| **Magenta / Accent** | Violet néon | `#bb9af7` |
| **Rouge / Alertes** | Rouge néon | `#f7768e` |
| **Vert** | Vert menthe | `#73daca` |
| **Jaune** | Ambre | `#e0af68` |

---

## ⌨️ Raccourcis Hyprland Associés

- Lancer une nouvelle fenêtre Kitty : <kbd>SUPER</kbd> + <kbd>Return</kbd> ou <kbd>SUPER</kbd> + <kbd>Q</kbd>
- Fermer la fenêtre active : <kbd>SUPER</kbd> + <kbd>C</kbd>
- Passer la fenêtre en mode flottant : <kbd>SUPER</kbd> + <kbd>V</kbd>
