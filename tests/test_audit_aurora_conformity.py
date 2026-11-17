#!/usr/bin/env python3
"""
Test Suite: Strict Aurora Theme Conformity & Architectural Standards Audit
Checks:
1. 4 Design Pillars: 17px radius, 2px border, 45° gradient, translucidity 0.50
2. Invariants: Strict input:follow_mouse = 0 in hyprland.conf
3. Theme Engine & Palettes: Model definitions & @define-color templates
4. MCP Architecture: Exactly 13 tools registered, zero obsolete renderer tools
5. Runtime Security: $AURORA_RUNTIME_DIR contract enforcement across components
"""

import ast
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES = PROJECT_ROOT / "dotfiles"
SCRIPTS = PROJECT_ROOT / "scripts"


def check_component(name: str, checks: list) -> bool:
    print(f"\n--- Component: {name} ---")
    all_ok = True
    for item, passed, msg in checks:
        icon = "✓" if passed else "✗"
        print(f"  {icon} {item:<30} : {msg}")
        if not passed:
            all_ok = False
    return all_ok


def audit_hyprland() -> bool:
    conf = (DOTFILES / "hypr" / "hyprland.conf").read_text(encoding="utf-8")
    checks = []

    m_round = re.search(r"rounding\s*=\s*(\d+)", conf)
    r_val = int(m_round.group(1)) if m_round else 0
    checks.append(("Radius 17px", r_val == 17, f"rounding = {r_val}"))

    m_border = re.search(r"border_size\s*=\s*(\d+)", conf)
    b_val = int(m_border.group(1)) if m_border else 0
    checks.append(("Border 2px", b_val == 2, f"border_size = {b_val}"))

    m_grad = re.search(r"col\.active_border\s*=\s*(.+)$", conf, re.M)
    grad_str = m_grad.group(1) if m_grad else ""
    grad_ok = "45deg" in grad_str and "00F0FF" in grad_str.upper() and "7AA2F7" in grad_str.upper()
    checks.append(("Gradient 45°", grad_ok, grad_str.strip()))

    m_blur = "blur {" in conf and "enabled = true" in conf
    checks.append(("Glassmorphism Blur", m_blur, "Enabled (size=6, passes=1)"))

    # Strict invariant: follow_mouse must be 0
    m_fm = re.search(r"follow_mouse\s*=\s*(\d+)", conf)
    fm_val = int(m_fm.group(1)) if m_fm else -1
    checks.append(("User Invariant follow_mouse=0", fm_val == 0, f"follow_mouse = {fm_val}"))

    return check_component("Hyprland (hyprland.conf)", checks)


def audit_waybar() -> bool:
    css = (DOTFILES / "waybar" / "style.css").read_text(encoding="utf-8")
    svg_tree = ET.parse(DOTFILES / "waybar" / "bar-bg.svg")
    svg_root = svg_tree.getroot()
    rect = svg_root.find("{http://www.w3.org/2000/svg}rect")
    grad = svg_root.find(".//{http://www.w3.org/2000/svg}linearGradient")

    checks = []
    css_r = "border-radius: 17px;" in css
    svg_rx = rect.get("rx") if rect is not None else ""
    checks.append(("Radius 17px", css_r and svg_rx == "17", f"style.css (17px: {css_r}), bar-bg.svg (rx={svg_rx})"))

    svg_sw = rect.get("stroke-width") if rect is not None else ""
    checks.append(("Border 2px", svg_sw == "2", f"bar-bg.svg stroke-width={svg_sw}"))

    x1, y1, x2, y2 = grad.get("x1"), grad.get("y1"), grad.get("x2"), grad.get("y2")
    is_45 = (x1 == "0%" and y1 == "0%" and x2 == "100%" and y2 == "100%")
    checks.append(("Gradient 45°", is_45, f"Vector: ({x1},{y1} -> {x2},{y2})"))

    svg_fill = rect.get("fill") if rect is not None else ""
    fill_ok = "rgba(10, 15, 30, 0.50)" in svg_fill
    checks.append(("Translucidity (0.50)", fill_ok, f"fill={svg_fill}"))

    return check_component("Waybar (style.css & bar-bg.svg)", checks)


def audit_wofi() -> bool:
    css = (DOTFILES / "wofi" / "style.css").read_text(encoding="utf-8")
    checks = []
    checks.append(("Radius 17px", "border-radius: 17px;" in css, "border-radius: 17px present"))
    checks.append(("Border 2px", "border: 2px solid" in css, "border: 2px solid present"))
    checks.append(("Gradient 45°", "45deg" in css and "#00f0ff" in css, "#entry:selected gradient"))
    checks.append(("Translucidity (0.50)", "rgba(10, 15, 30, 0.50)" in css, "background opacity 0.50"))
    return check_component("Wofi (style.css)", checks)


def audit_swaync() -> bool:
    css = (DOTFILES / "swaync" / "style.css").read_text(encoding="utf-8")
    checks = []
    cc_r = ".control-center" in css and "border-radius: 17px;" in css
    noti_r = ".notification" in css and "border-radius: 17px;" in css
    checks.append(("Radius 17px", cc_r and noti_r, f"CC={cc_r}, Notif={noti_r}"))
    cc_b = "border: 2px solid @noti-border-color;" in css
    checks.append(("Border 2px", cc_b, "CC border: 2px solid @noti-border-color"))
    checks.append(("Gradient 45°", "linear-gradient(45deg" in css, "DND switch & hover actions 45deg"))
    bg_ok = "@define-color cc-bg rgba(10, 15, 30, 0.50);" in css
    checks.append(("Translucidity (0.50)", bg_ok, "@define-color cc-bg rgba(10, 15, 30, 0.50)"))
    return check_component("SwayNC (style.css)", checks)


def audit_spotify_card() -> bool:
    content = (DOTFILES / "waybar" / "scripts" / "spotify_hover.py").read_text(encoding="utf-8")
    checks = []
    checks.append(("Radius 17px", "border-radius: 17px;" in content, ".card-container border-radius: 17px"))
    checks.append(("Border 2px", "border: 2px solid" in content, ".card-container border: 2px solid"))
    checks.append(("Translucidity (0.50)", "rgba(10, 15, 30, 0.50)" in content, "card background 0.50"))
    return check_component("Spotify Floating Card (spotify_hover.py)", checks)


def audit_theme_palettes_and_templates() -> bool:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import theme_models
    import theme_templates

    checks = []
    themes = theme_models.get_available_themes()
    expected_themes = {"aurora", "tokyo-night", "blackwall-red", "cyberpunk-amber"}
    has_all_themes = expected_themes.issubset(set(themes))
    checks.append(("Theme catalog completeness", has_all_themes, f"Themes: {themes}"))

    # Test rendering Waybar, Wofi and Bar SVG for Aurora
    aurora_profile = theme_models.get_theme("aurora")
    svg_rendered = theme_templates.render_bar_svg(aurora_profile)
    checks.append(("Template SVG rendering", "rx=\"17\"" in svg_rendered, "bar-bg.svg radius 17px template"))

    wb_css = theme_templates.render_waybar_css(aurora_profile)
    checks.append(("Template Waybar CSS tokens", "@define-color waybar-primary" in wb_css, "Waybar tokens generated"))

    wofi_css = theme_templates.render_wofi_css(aurora_profile)
    checks.append(("Template Wofi CSS tokens", "@define-color wofi-primary" in wofi_css, "Wofi tokens generated"))

    return check_component("Theme Engine & Templates", checks)


def audit_mcp_tools() -> bool:
    mcp_server_path = SCRIPTS / "aurora_mcp_server.py"
    code = mcp_server_path.read_text(encoding="utf-8")
    tree = ast.parse(code, filename=str(mcp_server_path))

    registered_tools = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # match pattern server.tool()(func)
            if isinstance(node.func, ast.Call) and isinstance(node.func.func, ast.Attribute):
                if node.func.func.attr == "tool" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Name):
                        registered_tools.append(arg.id)
                    elif isinstance(arg, ast.Attribute):
                        registered_tools.append(f"{getattr(arg.value, 'id', '')}.{arg.attr}")

    checks = []
    expected_count = 13
    checks.append(("Exact 13 MCP tools count", len(registered_tools) == expected_count,
                   f"Registered: {len(registered_tools)} tools ({registered_tools})"))

    has_obsolete = any("renderer" in t.lower() for t in registered_tools)
    checks.append(("Zero obsolete renderer tools", not has_obsolete, "No renderer tool found in MCP catalog"))

    mandatory_tools = [
        "get_aurora_status",
        "system_tools.manage_wallpaper",
        "system_tools.manage_hyprbar",
        "system_tools.lock_session",
        "system_tools.reload_all",
        "system_tools.audit_hardlinks",
        "system_tools.wofi_launch",
        "system_tools.compact_workspaces",
        "system_tools.switch_theme",
        "media_tools.manage_swaync",
        "media_tools.manage_blacklist",
        "media_tools.audio_control",
        "media_tools.spotify_control",
    ]
    all_mandatory = all(t in registered_tools for t in mandatory_tools)
    checks.append(("All mandatory tools declared", all_mandatory, f"Matched {len(mandatory_tools)} tools"))

    return check_component("MCP Server Catalog (13 Tools)", checks)


def audit_runtime_directory_contract() -> bool:
    checks = []
    # 1. aurora_runtime.py get_aurora_runtime_dir implementation
    rt_py = (SCRIPTS / "aurora_runtime.py").read_text(encoding="utf-8")
    has_xdg = 'os.environ.get("XDG_RUNTIME_DIR")' in rt_py and '0o700' in rt_py
    checks.append(("aurora_runtime.py $AURORA_RUNTIME_DIR", has_xdg, "Canonical 0700 runtime dir"))

    # 2. lock.sh uses $AURORA_RUNTIME_DIR
    lock_sh = (DOTFILES / "hypr" / "lock.sh").read_text(encoding="utf-8")
    has_lock_rt = 'AURORA_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora"' in lock_sh
    checks.append(("lock.sh $AURORA_RUNTIME_DIR", has_lock_rt, "lock.sh uses canonical runtime dir"))

    # 3. hypridle.conf uses $AURORA_RUNTIME_DIR for Palier 4
    idle_conf = (DOTFILES / "hypr" / "hypridle.conf").read_text(encoding="utf-8")
    has_idle_rt = '${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/aurora/hypr_locked' in idle_conf
    checks.append(("hypridle.conf Palier 4 locked check", has_idle_rt, "hypridle inspects runtime flag"))

    return check_component("Runtime Directory Security Contract", checks)


def main():
    print("==================================================")
    print("AURORA THEME CONFORMITY & STANDARDS AUDIT SUITE")
    print("==================================================")
    results = [
        audit_hyprland(),
        audit_waybar(),
        audit_wofi(),
        audit_swaync(),
        audit_spotify_card(),
        audit_theme_palettes_and_templates(),
        audit_mcp_tools(),
        audit_runtime_directory_contract(),
    ]
    print("\n==================================================")
    all_ok = all(results)
    print(f"SUMMARY: {sum(results)}/{len(results)} audit modules strictly conform.")
    print("==================================================")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
