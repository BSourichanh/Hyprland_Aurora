# Hyprland Dotfiles & Desktop Environment

Ce projet centralise les fichiers de configuration de votre environnement Hyprland sous Linux / Wayland.

## Structure du projet

```
hyprland_project/
├── dotfiles/
│   ├── hypr/        # Hyprland, hypridle, hyprlock, thèmes et scripts
│   ├── waybar/      # Barre d'état personnalisée (translucide, heure FR)
│   ├── wofi/        # Menu des applications / lanceur
│   └── kitty/       # Terminal Kitty
└── .gitignore       # Exclusion des fichiers temporaires et binaires compilés
```

## Liens Symboliques (Symlinks)

Les configurations réelles du système dans `~/.config/` pointent directement vers ce projet :

- `~/.config/hypr` ➔ `dotfiles/hypr`
- `~/.config/waybar` ➔ `dotfiles/waybar`
- `~/.config/wofi` ➔ `dotfiles/wofi`
- `~/.config/kitty` ➔ `dotfiles/kitty`

> **Note :** Toute modification effectuée dans ce dossier de projet est répercutée en direct sur votre système.

## Raccourcis utiles

- Recharger Hyprland & Waybar : <kbd>SUPER</kbd> + <kbd>SHIFT</kbd> + <kbd>R</kbd>
- Lanceur d'applications (Wofi) : <kbd>SUPER</kbd> + <kbd>R</kbd>
- Terminal Kitty : <kbd>SUPER</kbd> + <kbd>Return</kbd> ou <kbd>SUPER</kbd> + <kbd>Q</kbd>
- Verrouillage écran : <kbd>SUPER</kbd> + <kbd>L</kbd>
- Explorateur de fichiers : <kbd>SUPER</kbd> + <kbd>E</kbd>
