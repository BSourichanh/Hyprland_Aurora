#!/usr/bin/env python3
"""
Moteur de Profils Visuels & Palettes - Aurora OS Ecosystem
Fournit les modèles de données et l'API pour les thèmes d'ambiance de l'écosystème.
Composants couverts : Waybar, SwayNC, Wofi, Kitty, Hyprland.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union
import json
import sys


@dataclass(frozen=True)
class WaybarTheme:
    """Variables visuelles spécifiques à Waybar."""
    accent: str
    accent_secondary: str
    capsule_bg: str
    hover_bg: str
    border: str
    text: str
    text_bright: str
    text_subtle: str
    text_muted: str
    selected_fg: str
    alert_color: str


@dataclass(frozen=True)
class SwayNCTheme:
    """Variables visuelles spécifiques au centre de notification SwayNC."""
    accent: str
    border: str
    noti_bg: str
    noti_bg_darker: str
    noti_bg_hover: str
    noti_bg_focus: str
    button_bg: str
    button_hover: str
    text: str
    text_disabled: str
    alert_color: str


@dataclass(frozen=True)
class WofiTheme:
    """Variables visuelles spécifiques au lanceur Wofi."""
    accent: str
    border_neon: str
    window_bg: str
    input_bg: str
    selection_bg: str
    selected_fg: str
    text: str


@dataclass(frozen=True)
class KittyTheme:
    """Variables visuelles spécifiques au terminal Kitty."""
    cursor: str
    selection_bg: str
    selection_fg: str
    accent: str
    bg: str
    fg: str


@dataclass(frozen=True)
class ThemeProfile:
    """Profil complet d'ambiance visuelle du bureau."""
    name: str
    display_name: str
    description: str
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str
    waybar: WaybarTheme
    swaync: SwayNCTheme
    wofi: WofiTheme
    kitty: KittyTheme

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le profil en dictionnaire sérialisable."""
        return asdict(self)


THEMES: Dict[str, ThemeProfile] = {
    "aurora": ThemeProfile(
        name="aurora",
        display_name="Aurora Cyberpunk (Défaut)",
        description="Cyan néon, bleu électrique et violet profond sur verre fumé translucide.",
        primary_color="#00f0ff",
        secondary_color="#7aa2f7",
        accent_color="#9778d0",
        background_color="rgba(10, 15, 30, 0.50)",
        waybar=WaybarTheme(
            accent="#00f0ff",
            accent_secondary="#7aa2f7",
            capsule_bg="rgba(10, 15, 30, 0.50)",
            hover_bg="rgba(20, 30, 60, 0.70)",
            border="rgba(0, 240, 255, 0.60)",
            text="#e1e4f1",
            text_bright="#f1f5f9",
            text_subtle="#cbd5e1",
            text_muted="#7a8fae",
            selected_fg="#090727",
            alert_color="#f43f5e",
        ),
        swaync=SwayNCTheme(
            accent="#00f0ff",
            border="rgba(0, 240, 255, 0.65)",
            noti_bg="rgba(10, 15, 30, 0.80)",
            noti_bg_darker="rgba(10, 15, 30, 0.95)",
            noti_bg_hover="rgba(21, 46, 80, 0.70)",
            noti_bg_focus="rgba(21, 46, 80, 0.85)",
            button_bg="rgba(0, 240, 255, 0.15)",
            button_hover="#f43f5e",
            text="#e1e4f1",
            text_disabled="#7a8fae",
            alert_color="#f43f5e",
        ),
        wofi=WofiTheme(
            accent="#00f0ff",
            border_neon="rgba(0, 240, 255, 0.65)",
            window_bg="rgba(10, 15, 30, 0.50)",
            input_bg="rgba(21, 46, 80, 0.60)",
            selection_bg="rgba(0, 240, 255, 0.20)",
            selected_fg="#090727",
            text="#e1e4f1",
        ),
        kitty=KittyTheme(
            cursor="#00f0ff",
            selection_bg="#7aa2f7",
            selection_fg="#0f111a",
            accent="#00f0ff",
            bg="#0f111a",
            fg="#c0caf5",
        ),
    ),
    "tokyo-night": ThemeProfile(
        name="tokyo-night",
        display_name="Tokyo Night",
        description="Bleu nuit tokyoïte, cyan pastel et nuances magenta néon sur verre fumé 50%.",
        primary_color="#7aa2f7",
        secondary_color="#7dcfff",
        accent_color="#bb9af7",
        background_color="rgba(15, 17, 26, 0.50)",
        waybar=WaybarTheme(
            accent="#7aa2f7",
            accent_secondary="#7dcfff",
            capsule_bg="rgba(15, 17, 26, 0.50)",
            hover_bg="rgba(31, 35, 53, 0.75)",
            border="rgba(122, 162, 247, 0.60)",
            text="#c0caf5",
            text_bright="#dbe4ff",
            text_subtle="#a9b1d6",
            text_muted="#565f89",
            selected_fg="#0f111a",
            alert_color="#f7768e",
        ),
        swaync=SwayNCTheme(
            accent="#7aa2f7",
            border="rgba(122, 162, 247, 0.65)",
            noti_bg="rgba(15, 17, 26, 0.85)",
            noti_bg_darker="rgba(15, 17, 26, 0.95)",
            noti_bg_hover="rgba(31, 35, 53, 0.75)",
            noti_bg_focus="rgba(36, 40, 59, 0.85)",
            button_bg="rgba(122, 162, 247, 0.20)",
            button_hover="#f7768e",
            text="#c0caf5",
            text_disabled="#565f89",
            alert_color="#f7768e",
        ),
        wofi=WofiTheme(
            accent="#7dcfff",
            border_neon="rgba(122, 162, 247, 0.65)",
            window_bg="rgba(15, 17, 26, 0.50)",
            input_bg="rgba(31, 35, 53, 0.65)",
            selection_bg="rgba(122, 162, 247, 0.25)",
            selected_fg="#0f111a",
            text="#c0caf5",
        ),
        kitty=KittyTheme(
            cursor="#7dcfff",
            selection_bg="#7aa2f7",
            selection_fg="#0f111a",
            accent="#bb9af7",
            bg="#0f111a",
            fg="#c0caf5",
        ),
    ),
    "blackwall-red": ThemeProfile(
        name="blackwall-red",
        display_name="Blackwall Rogue IA",
        description="Rouge et rose néon agressifs, noir d'encre translucide et alertes Cyberpunk.",
        primary_color="#ff0055",
        secondary_color="#f43f5e",
        accent_color="#ff2a6d",
        background_color="rgba(8, 5, 10, 0.50)",
        waybar=WaybarTheme(
            accent="#ff0055",
            accent_secondary="#f43f5e",
            capsule_bg="rgba(8, 5, 10, 0.60)",
            hover_bg="rgba(45, 10, 22, 0.75)",
            border="rgba(255, 0, 85, 0.60)",
            text="#ffe4ea",
            text_bright="#fff1f4",
            text_subtle="#fbcfe8",
            text_muted="#a34d60",
            selected_fg="#08050a",
            alert_color="#ff2a6d",
        ),
        swaync=SwayNCTheme(
            accent="#ff0055",
            border="rgba(255, 0, 85, 0.65)",
            noti_bg="rgba(8, 5, 10, 0.90)",
            noti_bg_darker="rgba(8, 5, 10, 0.95)",
            noti_bg_hover="rgba(40, 10, 20, 0.80)",
            noti_bg_focus="rgba(55, 12, 28, 0.85)",
            button_bg="rgba(255, 0, 85, 0.20)",
            button_hover="#ff0055",
            text="#ffe4ea",
            text_disabled="#a34d60",
            alert_color="#ff2a6d",
        ),
        wofi=WofiTheme(
            accent="#ff0055",
            border_neon="rgba(255, 0, 85, 0.70)",
            window_bg="rgba(8, 5, 10, 0.50)",
            input_bg="rgba(40, 10, 20, 0.70)",
            selection_bg="rgba(255, 0, 85, 0.25)",
            selected_fg="#08050a",
            text="#ffe4ea",
        ),
        kitty=KittyTheme(
            cursor="#ff0055",
            selection_bg="#ff0055",
            selection_fg="#050508",
            accent="#f43f5e",
            bg="#050508",
            fg="#ffe4ea",
        ),
    ),
    "cyberpunk-amber": ThemeProfile(
        name="cyberpunk-amber",
        display_name="Cyberpunk Amber / 2077 Gold",
        description="Ambre chaud, or chromé et jaune néon industriel inspiré de Night City.",
        primary_color="#ffb800",
        secondary_color="#f0db4f",
        accent_color="#e0af68",
        background_color="rgba(15, 14, 10, 0.50)",
        waybar=WaybarTheme(
            accent="#ffb800",
            accent_secondary="#f0db4f",
            capsule_bg="rgba(15, 14, 10, 0.60)",
            hover_bg="rgba(48, 38, 14, 0.75)",
            border="rgba(255, 184, 0, 0.60)",
            text="#fdf6e2",
            text_bright="#fffbeb",
            text_subtle="#f5e6c4",
            text_muted="#998450",
            selected_fg="#0c0c0e",
            alert_color="#f97316",
        ),
        swaync=SwayNCTheme(
            accent="#ffb800",
            border="rgba(255, 184, 0, 0.65)",
            noti_bg="rgba(15, 14, 10, 0.85)",
            noti_bg_darker="rgba(15, 14, 10, 0.95)",
            noti_bg_hover="rgba(45, 38, 15, 0.80)",
            noti_bg_focus="rgba(60, 50, 18, 0.85)",
            button_bg="rgba(255, 184, 0, 0.20)",
            button_hover="#f0db4f",
            text="#fdf6e2",
            text_disabled="#998450",
            alert_color="#f97316",
        ),
        wofi=WofiTheme(
            accent="#ffb800",
            border_neon="rgba(255, 184, 0, 0.65)",
            window_bg="rgba(15, 14, 10, 0.50)",
            input_bg="rgba(45, 38, 15, 0.65)",
            selection_bg="rgba(255, 184, 0, 0.25)",
            selected_fg="#0c0c0e",
            text="#fdf6e2",
        ),
        kitty=KittyTheme(
            cursor="#f0db4f",
            selection_bg="#ffb800",
            selection_fg="#0c0c0e",
            accent="#ffb800",
            bg="#0c0c0e",
            fg="#fdf6e2",
        ),
    ),
}


def get_available_themes() -> List[str]:
    """Retourne la liste ordonnée des identifiants de thèmes disponibles."""
    return list(THEMES.keys())


def get_theme(name: str) -> Optional[ThemeProfile]:
    """Récupère un profil de thème par son identifiant."""
    return THEMES.get(name.lower().strip())


def generate_theme_variables(theme: Union[str, ThemeProfile]) -> Dict[str, Any]:
    """Génère le dictionnaire complet de variables de style prêtes pour l'injection."""
    if isinstance(theme, str):
        profile = get_theme(theme)
        if not profile:
            raise ValueError(f"Thème inconnu '{theme}'. Disponibles: {get_available_themes()}")
    elif isinstance(theme, ThemeProfile):
        profile = theme
    else:
        raise TypeError(f"Type attendu: str ou ThemeProfile, reçu: {type(theme)}")

    return {
        "THEME_NAME": profile.name,
        "THEME_DISPLAY": profile.display_name,
        "THEME_DESCRIPTION": profile.description,
        "COLOR_PRIMARY": profile.primary_color,
        "COLOR_SECONDARY": profile.secondary_color,
        "COLOR_ACCENT": profile.accent_color,
        "COLOR_BG": profile.background_color,
        "WAYBAR_ACCENT": profile.waybar.accent,
        "WAYBAR_ACCENT_SEC": profile.waybar.accent_secondary,
        "WAYBAR_CAPSULE_BG": profile.waybar.capsule_bg,
        "WAYBAR_HOVER_BG": profile.waybar.hover_bg,
        "WAYBAR_BORDER": profile.waybar.border,
        "WAYBAR_TEXT": profile.waybar.text,
        "WAYBAR_TEXT_MUTED": profile.waybar.text_muted,
        "SWAYNC_ACCENT": profile.swaync.accent,
        "SWAYNC_BORDER": profile.swaync.border,
        "SWAYNC_NOTI_BG": profile.swaync.noti_bg,
        "SWAYNC_NOTI_BG_DARKER": profile.swaync.noti_bg_darker,
        "SWAYNC_NOTI_BG_HOVER": profile.swaync.noti_bg_hover,
        "SWAYNC_NOTI_BG_FOCUS": profile.swaync.noti_bg_focus,
        "SWAYNC_BTN_BG": profile.swaync.button_bg,
        "SWAYNC_BTN_HOVER": profile.swaync.button_hover,
        "SWAYNC_TEXT": profile.swaync.text,
        "SWAYNC_TEXT_DISABLED": profile.swaync.text_disabled,
        "WOFI_ACCENT": profile.wofi.accent,
        "WOFI_BORDER": profile.wofi.border_neon,
        "WOFI_WINDOW_BG": profile.wofi.window_bg,
        "WOFI_INPUT_BG": profile.wofi.input_bg,
        "WOFI_SELECTION_BG": profile.wofi.selection_bg,
        "WOFI_TEXT": profile.wofi.text,
        "KITTY_CURSOR": profile.kitty.cursor,
        "KITTY_SELECTION_BG": profile.kitty.selection_bg,
        "KITTY_SELECTION_FG": profile.kitty.selection_fg,
        "KITTY_ACCENT": profile.kitty.accent,
        "KITTY_BG": profile.kitty.bg,
        "KITTY_FG": profile.kitty.fg,
        "profile": profile.to_dict(),
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        print(json.dumps(get_available_themes(), indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] in ("show", "export"):
        t = get_theme(sys.argv[2])
        if t:
            print(json.dumps(generate_theme_variables(t), indent=2))
        else:
            print(f"Erreur: Thème '{sys.argv[2]}' introuvable.", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Thèmes d'ambiance disponibles ({len(THEMES)}) :")
        for k, v in THEMES.items():
            print(f"  - {k:18} : {v.display_name} [{v.primary_color}]")
