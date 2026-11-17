#!/usr/bin/env python3
"""
Theme Switcher & Dynamic Visual Palette Orchestrator - Aurora OS
Synchronizes Waybar, SwayNC, Wofi, Kitty, and Hyprland in-place
without breaking existing hardlinks.
"""

import argparse
import contextlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from aurora_runtime import get_lock_state  # noqa: E402
from theme_models import ThemeProfile, get_available_themes, get_theme  # noqa: E402
from theme_templates import (  # noqa: E402
    render_bar_svg,
    render_waybar_css,
    render_waybar_palette_block,
    render_wofi_css,
    render_wofi_palette_block,
)

PROJECT_DIR = SCRIPT_DIR.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
THEME_STATE_FILE = PROJECT_DIR / ".theme_state"


def write_inplace(path: Path, content: str) -> None:
    """Overwrites file in-place validating UTF-8 encoding and preserving inode/hardlinks."""
    content.encode("utf-8")
    if path.exists():
        orig_inode = path.stat().st_ino
        with open(path, "r+", encoding="utf-8") as f:
            f.seek(0)
            f.write(content)
            f.truncate()
        new_inode = path.stat().st_ino
        if orig_inode != new_inode:
            raise RuntimeError(f"Rupture de hardlink sur {path} (inode {orig_inode} != {new_inode})")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def _replace_sentinel_block(text: str, start_marker: str, end_marker: str, block: str) -> str:
    """Replaces block delimited by sentinels without backslash regex interpretation."""
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    return re.sub(pattern, lambda _: block, text, flags=re.DOTALL)


def _update_css_with_palette(
    css_path: Path,
    palette_token: str,
    render_palette: Callable[[ThemeProfile], str],
    render_full: Callable[[ThemeProfile], str],
    profile: ThemeProfile,
) -> None:
    """Updates sentinel palette block when rules consume @define-color tokens, else regenerates CSS."""
    if css_path.exists():
        text = css_path.read_text(encoding="utf-8")
        if (
            "/* AURORA_PALETTE_START */" in text
            and "/* AURORA_PALETTE_END */" in text
            and palette_token in text
        ):
            new_text = _replace_sentinel_block(
                text,
                "/* AURORA_PALETTE_START */",
                "/* AURORA_PALETTE_END */",
                render_palette(profile),
            )
            write_inplace(css_path, new_text)
            return
    write_inplace(css_path, render_full(profile))


def update_bar_svg(profile: ThemeProfile) -> None:
    """Updates Waybar SVG gradient bar background in-place."""
    write_inplace(DOTFILES_DIR / "waybar" / "bar-bg.svg", render_bar_svg(profile))


def update_waybar_css(profile: ThemeProfile) -> None:
    """Updates Waybar stylesheet in-place (preserves local rules when @waybar-* tokens are used)."""
    _update_css_with_palette(
        DOTFILES_DIR / "waybar" / "style.css",
        "@waybar-primary",
        render_waybar_palette_block,
        render_waybar_css,
        profile,
    )


def update_swaync_css(profile: ThemeProfile) -> None:
    """Updates SwayNC GTK stylesheet @define-color definitions in-place with sentinel guards."""
    path = DOTFILES_DIR / "swaync" / "style.css"
    text = path.read_text(encoding="utf-8")
    snc = profile.swaync
    def_colors = f"""/* AURORA_PALETTE_START */
@define-color cc-bg {profile.background_color};
@define-color noti-border-color {snc.border};
@define-color noti-bg {snc.noti_bg};
@define-color noti-bg-darker {snc.noti_bg_darker};
@define-color noti-bg-hover {snc.noti_bg_hover};
@define-color noti-bg-focus {snc.noti_bg_focus};
@define-color noti-close-bg {snc.button_bg};
@define-color noti-close-bg-hover {snc.button_hover};

@define-color text-color {snc.text};
@define-color text-color-disabled {snc.text_disabled};
@define-color cyan-primary {profile.primary_color};
@define-color blue-secondary {profile.secondary_color};
@define-color violet-accent {profile.accent_color};
@define-color alert-red {snc.alert_color};
/* AURORA_PALETTE_END */"""

    if "/* AURORA_PALETTE_START */" in text and "/* AURORA_PALETTE_END */" in text:
        new_text = _replace_sentinel_block(text, "/* AURORA_PALETTE_START */", "/* AURORA_PALETTE_END */", def_colors)
    else:
        new_text = re.sub(r"@define-color cc-bg.*?(?=\n\n\*)", lambda _: def_colors, text, flags=re.DOTALL)
    write_inplace(path, new_text)


def update_wofi_css(profile: ThemeProfile) -> None:
    """Updates Wofi stylesheet in-place (preserves local rules when @wofi-* tokens are used)."""
    _update_css_with_palette(
        DOTFILES_DIR / "wofi" / "style.css",
        "@wofi-primary",
        render_wofi_palette_block,
        render_wofi_css,
        profile,
    )


def update_kitty_conf(profile: ThemeProfile) -> None:
    """Updates Kitty terminal color palette in-place with sentinel guards."""
    path = DOTFILES_DIR / "kitty" / "kitty.conf"
    text = path.read_text(encoding="utf-8")
    colors_block = f"""# AURORA_PALETTE_START
# Colors ({profile.display_name})
background {profile.kitty.bg}
foreground {profile.kitty.fg}
selection_background {profile.kitty.selection_bg}
selection_foreground {profile.kitty.selection_fg}
cursor {profile.kitty.cursor}
cursor_text_color {profile.kitty.selection_fg}

# Black
color0 #414868
color8 #414868

# Red
color1 #f7768e
color9 #f7768e

# Green
color2 #73daca
color10 #73daca

# Yellow
color3 #e0af68
color11 #e0af68

# Blue
color4 {profile.secondary_color}
color12 {profile.secondary_color}

# Magenta
color5 {profile.accent_color}
color13 {profile.accent_color}

# Cyan
color6 {profile.primary_color}
color14 {profile.primary_color}

# White
color7 {profile.kitty.fg}
color15 {profile.kitty.fg}
# AURORA_PALETTE_END"""

    if "# AURORA_PALETTE_START" in text and "# AURORA_PALETTE_END" in text:
        new_text = _replace_sentinel_block(text, "# AURORA_PALETTE_START", "# AURORA_PALETTE_END", colors_block)
    else:
        new_text = re.sub(r"# Colors.*", lambda _: colors_block, text, flags=re.DOTALL)
    write_inplace(path, new_text)


def update_hyprland_conf(profile: ThemeProfile) -> bool:
    """Updates Hyprland active and inactive window border gradient in-place."""
    path = DOTFILES_DIR / "hypr" / "hyprland.conf"
    text = path.read_text(encoding="utf-8")

    hp = profile.primary_color.lstrip("#").upper()
    hs = profile.secondary_color.lstrip("#").upper()
    ha = profile.accent_color.lstrip("#").upper()

    inactive_map = {
        "aurora": "04404aaa",
        "tokyo-night": "1F2335aa",
        "blackwall-red": "280A14aa",
        "cyberpunk-amber": "2D260Faa",
    }
    inact = inactive_map.get(profile.name, f"{hs[:6]}aa")

    new_active = f"col.active_border = rgba({hp}FF) rgba({hs}FF) rgba({ha}FF) rgba({hp}FF) 45deg"
    new_inactive = f"col.inactive_border = rgba({inact})"

    text_mod = re.sub(r"col\.active_border\s*=.*", lambda _: new_active, text)
    text_mod = re.sub(r"col\.inactive_border\s*=.*", lambda _: new_inactive, text_mod)

    if text_mod != text:
        write_inplace(path, text_mod)
        return True
    return False


def _run_reload_cmd(cmd: List[str], timeout: float) -> bool:
    """Executes a subsystem reload command without raising on missing binary or timeout."""
    try:
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        return res.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"Avertissement rechargement ({cmd[0]}): {exc}", file=sys.stderr)
        return False


def reload_subsystems(hypr_reload: bool = True) -> Dict[str, Any]:
    """Sends hot-reload signals across the desktop components without bypassing session lock."""
    results: Dict[str, Any] = {}
    locked = get_lock_state()["locked"]

    if locked:
        results["waybar"] = "skipped_locked"
    elif _run_reload_cmd(["killall", "-SIGUSR2", "waybar"], 3):
        results["waybar"] = True
    else:
        hyprbar = PROJECT_DIR / "scripts" / "hyprbar"
        results["waybar"] = _run_reload_cmd([str(hyprbar), "restart"], 10) if hyprbar.exists() else False

    snc_cfg = _run_reload_cmd(["swaync-client", "-R"], 3)
    snc_css = _run_reload_cmd(["swaync-client", "-rs"], 3)
    results["swaync"] = snc_cfg and snc_css

    try:
        has_kitty = subprocess.run(["pgrep", "-x", "kitty"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2)
        if has_kitty.returncode == 0:
            results["kitty"] = _run_reload_cmd(["killall", "-SIGUSR1", "kitty"], 3)
        else:
            results["kitty"] = "skipped_not_running"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"Avertissement rechargement (pgrep): {exc}", file=sys.stderr)
        results["kitty"] = False

    if hypr_reload and not locked:
        results["hyprland"] = _run_reload_cmd(["hyprctl", "reload"], 5)
    elif hypr_reload and locked:
        results["hyprland"] = "skipped_locked"

    return results


def send_theme_notification(profile: ThemeProfile, reloads: Dict[str, Any]) -> bool:
    """Emits notification via notify-send summarizing actual reloaded subsystems."""
    active_items = [(k, v) for k, v in reloads.items() if isinstance(v, bool)]
    ok_count = sum(1 for _, v in active_items if v)
    total = len(active_items)
    synced_names = ", ".join(k.capitalize() for k, v in reloads.items() if v is True) or "fichiers mis à jour"

    title = "Aurora OS — Thème Appliqué"
    body = (
        f"Thème : {profile.display_name} ({profile.name})\n"
        f"Palette : {profile.primary_color} | {profile.secondary_color} | {profile.accent_color}\n"
        f"Composants rechargés ({ok_count}/{total}) : {synced_names}"
    )
    cmd = [
        "notify-send",
        "-a", "Aurora Theme",
        "-u", "normal",
        "-c", "system",
        "-t", "3500",
        "-i", "preferences-desktop-theme",
        title,
        body,
    ]
    with contextlib.suppress(Exception):
        res = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2.0)
        return res.returncode == 0
    return False


def apply_theme(theme_name: str) -> Dict[str, Any]:
    """Main orchestrator applying a visual profile in-place across all subsystems."""
    profile = get_theme(theme_name)
    if not profile:
        raise ValueError(f"Thème '{theme_name}' inconnu. Disponibles: {get_available_themes()}")

    update_bar_svg(profile)
    update_waybar_css(profile)
    update_swaync_css(profile)
    update_wofi_css(profile)
    update_kitty_conf(profile)
    hypr_changed = update_hyprland_conf(profile)

    reloads = reload_subsystems(hypr_reload=hypr_changed)
    THEME_STATE_FILE.write_text(profile.name, encoding="utf-8")
    notif_sent = send_theme_notification(profile, reloads)

    return {
        "ok": True,
        "theme": profile.name,
        "display_name": profile.display_name,
        "palette": {
            "primary": profile.primary_color,
            "secondary": profile.secondary_color,
            "accent": profile.accent_color,
            "background": profile.background_color,
        },
        "reloads": reloads,
        "notification": notif_sent,
    }


def get_current_theme_name() -> str:
    """Reads current theme from state file, falling back to 'aurora'."""
    if THEME_STATE_FILE.exists():
        with contextlib.suppress(Exception):
            return THEME_STATE_FILE.read_text(encoding="utf-8").strip()
    return "aurora"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aurora Visual Theme Switcher & Hot-Reload CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_apply = sub.add_parser("apply", help="Appliquer un thème d'ambiance visuelle")
    p_apply.add_argument("theme", choices=get_available_themes(), help="Nom du thème")

    sub.add_parser("list", help="Lister les thèmes disponibles")
    sub.add_parser("status", help="Afficher l'état du thème actif")

    args = parser.parse_args()

    if args.command == "list":
        print(f"Thèmes d'ambiance disponibles ({len(get_available_themes())}) :")
        for name in get_available_themes():
            t = get_theme(name)
            marker = " (actif)" if name == get_current_theme_name() else ""
            print(f"  • {name:16} : {t.display_name} [{t.primary_color}]{marker}")
    elif args.command == "status":
        curr = get_current_theme_name()
        t = get_theme(curr)
        print(f"Thème actif : {curr} ({t.display_name if t else 'Inconnu'})")
        if t:
            print(f"  • Primaire    : {t.primary_color}")
            print(f"  • Secondaire  : {t.secondary_color}")
            print(f"  • Accent      : {t.accent_color}")
            print(f"  • Arrière-plan: {t.background_color}")
    elif args.command == "apply":
        try:
            res = apply_theme(args.theme)
            print(f"✓ Thème '{res['theme']}' ({res['display_name']}) appliqué avec succès.")
            print(f"  • Signaux envoyés : {res['reloads']}")
            if res.get("notification"):
                print("  • Notification riche SwayNC émise.")
        except Exception as exc:
            print(f"✗ Erreur lors de l'application du thème : {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
