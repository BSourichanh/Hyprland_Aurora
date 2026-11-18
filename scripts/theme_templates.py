#!/usr/bin/env python3
"""
Theme Templates & Generators - Aurora OS Ecosystem
Provides template rendering for Waybar GTK CSS, Wofi stylesheet, and SVG vector bar.
"""

import re
from typing import Tuple

try:
    from theme_models import ThemeProfile
except ImportError:
    from scripts.theme_models import ThemeProfile

HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{6}$")


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Converts a hex color string (#rrggbb) to an (R, G, B) integer tuple with validation."""
    if not isinstance(hex_str, str):
        return 0, 240, 255
    h = hex_str.strip().lstrip("#")
    if len(h) >= 6 and HEX_PATTERN.match(h[:6]):
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            return 0, 240, 255
    return 0, 240, 255


def render_bar_svg(profile: ThemeProfile) -> str:
    """Renders the SVG gradient bar background adhering to Aurora 45deg and 17px radius."""
    bg = profile.background_color
    if bg.startswith("#"):
        r, g, b = hex_to_rgb(bg)
        bg = f"rgba({r}, {g}, {b}, 0.50)"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1900" height="34" viewBox="0 0 1900 34" preserveAspectRatio="none">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{profile.primary_color}" />
      <stop offset="50%" stop-color="{profile.secondary_color}" />
      <stop offset="100%" stop-color="{profile.accent_color}" />
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="1898" height="32" rx="17" ry="17" fill="{bg}" stroke="url(#grad)" stroke-width="2" />
</svg>"""


def render_waybar_palette_block(profile: ThemeProfile) -> str:
    """Renders sentinel-guarded @define-color variables for Waybar CSS."""
    pr, pg, pb = hex_to_rgb(profile.primary_color)
    sr, sg, sb = hex_to_rgb(profile.secondary_color)
    wb = profile.waybar
    return f"""/* AURORA_PALETTE_START */
@define-color waybar-primary {profile.primary_color};
@define-color waybar-secondary {profile.secondary_color};
@define-color waybar-accent {profile.accent_color};
@define-color waybar-highlight {wb.accent};
@define-color waybar-highlight-secondary {wb.accent_secondary};
@define-color waybar-capsule-bg {wb.capsule_bg};
@define-color waybar-hover-bg {wb.hover_bg};
@define-color waybar-border {wb.border};
@define-color waybar-text {wb.text};
@define-color waybar-text-bright {wb.text_bright};
@define-color waybar-text-subtle {wb.text_subtle};
@define-color waybar-text-muted {wb.text_muted};
@define-color waybar-selected-fg {wb.selected_fg};
@define-color waybar-alert {wb.alert_color};
@define-color waybar-warning #e0af68;
@define-color waybar-visible-bg rgba({pr}, {pg}, {pb}, 0.15);
@define-color waybar-visible-glow rgba({pr}, {pg}, {pb}, 0.25);
@define-color waybar-active-glow rgba({pr}, {pg}, {pb}, 0.55);
@define-color waybar-progress-border rgba({sr}, {sg}, {sb}, 0.25);
/* AURORA_PALETTE_END */"""


def render_waybar_css(profile: ThemeProfile) -> str:
    """Renders Waybar GTK stylesheet consuming @define-color variables from the palette block."""
    return f"""{render_waybar_palette_block(profile)}

* {{
    border: none;
    border-radius: 0;
    font-family: "Noto Sans", "JetBrainsMono Nerd Font", "FontAwesome", sans-serif;
    font-size: 13px;
    font-weight: 500;
    min-height: 0;
}}

/* Barre Waybar translucide avec dégradé vectoriel continu */
window#waybar {{
    background-color: transparent;
    background-image: url('bar-bg.svg');
    background-repeat: no-repeat;
    background-size: 100% 34px;
    background-position: center;
    border: none;
    border-radius: 17px;
    color: @waybar-text;
    box-shadow: none;
}}

/* Espaces de travail */
#workspaces {{
    background: @waybar-capsule-bg;
    border: 1.5px solid @waybar-border;
    border-radius: 10px;
    margin: 3px 4px;
    padding: 1px 3px;
}}

#workspaces button {{
    padding: 0 8px;
    margin: 1px 2px;
    color: @waybar-text-muted;
    background: transparent;
    border: 1.5px solid transparent;
    border-radius: 8px;
    transition: all 0.2s ease-in-out;
}}

#workspaces button:hover {{
    background: rgba(255, 255, 255, 0.12);
    color: @waybar-highlight;
}}

/* Workspace affiché à l'écran (sur moniteur non focus) */
#workspaces button.visible {{
    background: @waybar-visible-bg;
    border: 1.5px solid @waybar-border;
    color: @waybar-highlight;
    font-weight: 600;
    box-shadow: 0 0 6px @waybar-visible-glow;
}}

/* Workspace actif / avec le focus clavier */
#workspaces button.active {{
    background: linear-gradient(45deg, @waybar-primary, @waybar-secondary, @waybar-accent);
    border: 1.5px solid transparent;
    color: @waybar-selected-fg;
    font-weight: 700;
    box-shadow: 0 0 10px @waybar-active-glow;
}}

#workspaces button.urgent {{
    background: @waybar-alert;
    color: #ffffff;
    font-weight: 700;
}}

/* Horloge centrale translucide */
#clock {{
    padding: 0 14px;
    margin: 3px 0;
    color: @waybar-text-bright;
    font-weight: 600;
    border: 1.5px solid @waybar-border;
    border-radius: 10px;
    background: @waybar-capsule-bg;
}}

/* Modules de droite */
#custom-gpu, #cpu, #memory, #pulseaudio, #network, #custom-notification, #tray {{
    padding: 0 8px;
    margin: 3px 1px;
    color: @waybar-text;
    border: 1.5px solid @waybar-border;
    border-radius: 10px;
    background: @waybar-capsule-bg;
}}

#cpu.warning, #memory.warning {{
    border-color: @waybar-warning;
    color: @waybar-warning;
}}

#cpu.critical, #memory.critical {{
    border-color: @waybar-alert;
    color: @waybar-alert;
}}

#tray > .passive {{
    -gtk-icon-effect: dim;
}}

#tray > .needs-attention {{
    -gtk-icon-effect: highlight;
    background-color: @waybar-alert;
}}

/* Conteneur Spotify Mini-Player */
#spotify-player {{
    border: none;
    background: transparent;
    padding: 0;
    margin: 0;
}}

/* Module Media Spotify */
#mpris {{
    padding: 0 8px 0 12px;
    margin: 3px 0;
    color: @waybar-text-bright;
    font-weight: 600;
    border: 1.5px solid @waybar-border;
    border-right: none;
    border-radius: 10px 0 0 10px;
    background: @waybar-capsule-bg;
    transition: all 0.2s ease-in-out;
}}

#mpris:hover {{
    background: @waybar-hover-bg;
}}

#mpris.paused {{
    color: @waybar-text-muted;
}}

/* Barre de progression avec délimiteurs subtils */
#custom-spotify-progress {{
    padding: 0 10px;
    margin: 3px 0;
    font-size: 11.5px;
    color: @waybar-text-subtle;
    border-top: 1.5px solid @waybar-border;
    border-bottom: 1.5px solid @waybar-border;
    border-left: 1px solid @waybar-progress-border;
    border-right: 1px solid @waybar-progress-border;
    background: @waybar-capsule-bg;
    transition: all 0.2s ease-in-out;
}}

#custom-spotify-progress:hover {{
    background: @waybar-hover-bg;
}}

/* Boutons de navigation */
#custom-spotify-prev,
#custom-spotify-play-pause {{
    padding: 0 6px;
    margin: 3px 0;
    color: @waybar-highlight-secondary;
    border-top: 1.5px solid @waybar-border;
    border-bottom: 1.5px solid @waybar-border;
    border-left: none;
    border-right: none;
    background: @waybar-capsule-bg;
    transition: all 0.2s ease-in-out;
}}

#custom-spotify-next {{
    padding: 0 12px 0 6px;
    margin: 3px 0;
    color: @waybar-highlight-secondary;
    border: 1.5px solid @waybar-border;
    border-left: none;
    border-radius: 0 10px 10px 0;
    background: @waybar-capsule-bg;
    transition: all 0.2s ease-in-out;
}}

#custom-spotify-prev:hover,
#custom-spotify-play-pause:hover,
#custom-spotify-next:hover {{
    color: @waybar-highlight;
    background: @waybar-hover-bg;
}}

#mpris.stopped,
#custom-spotify-progress.stopped,
#custom-spotify-progress.empty,
#custom-spotify-prev.stopped,
#custom-spotify-play-pause.stopped,
#custom-spotify-next.stopped {{
    border: none;
    background: transparent;
    background-image: none;
    padding: 0;
    margin: 0;
}}
"""


def render_wofi_palette_block(profile: ThemeProfile) -> str:
    """Renders sentinel-guarded @define-color variables for Wofi CSS."""
    pr, pg, pb = hex_to_rgb(profile.primary_color)
    sr, sg, sb = hex_to_rgb(profile.secondary_color)
    wf = profile.wofi
    return f"""/* AURORA_PALETTE_START */
@define-color wofi-primary {profile.primary_color};
@define-color wofi-secondary {profile.secondary_color};
@define-color wofi-accent-grad {profile.accent_color};
@define-color wofi-accent {wf.accent};
@define-color wofi-border {wf.border_neon};
@define-color wofi-window-bg {wf.window_bg};
@define-color wofi-input-bg {wf.input_bg};
@define-color wofi-selection-bg {wf.selection_bg};
@define-color wofi-selected-fg {wf.selected_fg};
@define-color wofi-text {wf.text};
@define-color wofi-window-glow rgba({pr}, {pg}, {pb}, 0.20);
@define-color wofi-input-border rgba({sr}, {sg}, {sb}, 0.50);
@define-color wofi-focus-glow rgba({pr}, {pg}, {pb}, 0.60);
@define-color wofi-hover-border rgba({pr}, {pg}, {pb}, 0.50);
@define-color wofi-selected-glow rgba({pr}, {pg}, {pb}, 0.40);
/* AURORA_PALETTE_END */"""


def render_wofi_css(profile: ThemeProfile) -> str:
    """Renders Wofi stylesheet consuming @define-color variables from the palette block."""
    return f"""{render_wofi_palette_block(profile)}

window {{
    margin: 0px;
    border: 2px solid @wofi-border;
    border-radius: 17px;
    background-color: @wofi-window-bg;
    font-family: "Noto Sans", sans-serif;
    font-size: 14px;
    color: @wofi-text;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 18px @wofi-window-glow;
}}

#input {{
    margin: 14px;
    padding: 10px 14px;
    border: 1px solid @wofi-input-border;
    border-radius: 12px;
    color: @wofi-text;
    background-color: @wofi-input-bg;
    font-size: 14px;
}}

#input:focus {{
    border: 1.5px solid @wofi-accent;
    box-shadow: 0 0 10px @wofi-focus-glow;
}}

#inner-box, #outer-box {{
    background-color: transparent;
}}

#inner-box {{
    margin: 4px 14px 14px 14px;
}}

#outer-box, #scroll {{
    margin: 0px;
}}

#text {{
    margin: 5px 12px;
    color: @wofi-text;
}}

#entry {{
    padding: 8px 12px;
    margin: 2px 0px;
    border-radius: 12px;
    border: 1px solid transparent;
    background-color: transparent;
    transition: all 0.15s ease-in-out;
}}

#entry:hover,
#unselected:hover {{
    background-color: @wofi-selection-bg;
    border: 1px solid @wofi-hover-border;
}}

#entry:hover #text,
#unselected:hover #text {{
    color: @wofi-accent;
}}

#entry:selected {{
    background: linear-gradient(45deg, @wofi-primary, @wofi-secondary, @wofi-accent-grad);
    border: 1px solid @wofi-primary;
    color: @wofi-selected-fg;
    font-weight: bold;
    box-shadow: 0 0 10px @wofi-selected-glow;
}}

#entry:selected #text,
#entry:selected:hover #text {{
    color: @wofi-selected-fg;
    font-weight: bold;
}}

#entry:selected:hover {{
    background: linear-gradient(45deg, @wofi-primary, @wofi-secondary, @wofi-accent-grad);
    border: 1px solid @wofi-primary;
    box-shadow: 0 0 14px @wofi-focus-glow;
}}
"""
