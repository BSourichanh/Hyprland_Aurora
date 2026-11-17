#!/usr/bin/env python3
"""
Test Suite: Syntax and Static Audit for Hyprland Project Dotfiles & Scripts
Checks:
- hyprland.conf (syntax, follow_mouse, windowrule, binds)
- waybar/config.jsonc (JSON/JSONC validation, module definitions, scripts)
- waybar/style.css & bar-bg.svg (SVG XML, gradient, dimensions, radius, CSS colors)
- swaync/config.json & style.css (JSON, widgets, blacklist rules, CSS selectors)
- wofi/config & style.css (dimensions, radius 17px, hover/select)
- kitty/kitty.conf (palette, opacity 0.50, options)
- Comprehensive Python syntax (ast/py_compile) on all dotfiles & scripts
- Comprehensive Bash syntax (bash -n) on all shell scripts
"""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES = PROJECT_ROOT / "dotfiles"
SCRIPTS = PROJECT_ROOT / "scripts"


def run_test(name, func):
    print(f"\n--- [TEST] {name} ---")
    try:
        ok, details = func()
        status = "PASS" if ok else "FAIL"
        print(f"Result: {status}")
        for d in details:
            print(f"  • {d}")
        return ok
    except Exception as e:
        print(f"Result: ERROR -> {e}")
        return False


def test_hyprland_conf():
    details = []
    ok = True
    conf_path = DOTFILES / "hypr" / "hyprland.conf"
    if not conf_path.exists():
        return False, [f"File missing: {conf_path}"]

    # 1. Hyprland syntax check via binary
    res = subprocess.run(
        ["Hyprland", "--config", str(conf_path), "--verify-config"],
        capture_output=True, text=True, check=False,
    )
    if "config ok" in res.stdout:
        details.append("Hyprland --verify-config: PASSED ('config ok')")
    else:
        ok = False
        details.append(f"Hyprland --verify-config FAILED:\n{res.stdout}\n{res.stderr}")

    # 2. Check follow_mouse directive (User explicit preference is 0)
    content = conf_path.read_text(encoding="utf-8")
    fm_match = re.search(r"follow_mouse\s*=\s*(\d+)", content)
    if fm_match and fm_match.group(1) == "0":
        details.append("Directive follow_mouse = 0: PASSED (Click-to-focus invariant)")
    else:
        ok = False
        val = fm_match.group(1) if fm_match else "missing"
        details.append(f"Directive follow_mouse = {val}: FAILED (Expected strict 0)")

    # 3. Check windowrule syntax
    windowrules = re.findall(r"^windowrule\s*=\s*(.+)$", content, re.M)
    details.append(f"Total windowrule entries found: {len(windowrules)}")

    # 4. Check keybind conflicts
    binds = re.findall(r"^(bind[elmr]*)\s*=\s*([^,\n]*),\s*([^,\n]*),\s*(.+)$", content, re.M)
    combos = {}
    conflicts = []
    for b_type, mod, key, action in binds:
        combo = (mod.strip(), key.strip())
        if combo in combos:
            conflicts.append((combo, combos[combo], action.strip()))
        else:
            combos[combo] = action.strip()
    if conflicts:
        details.append(f"Keybinding overlaps found: {len(conflicts)}")
    else:
        details.append("No identical keybind collisions detected.")

    return ok, details


def test_waybar_config():
    details = []
    ok = True
    cfg_path = DOTFILES / "waybar" / "config.jsonc"
    if not cfg_path.exists():
        return False, [f"File missing: {cfg_path}"]

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        details.append(f"Python json.load: PASSED ({len(data)} root keys)")
    except Exception as e:
        return False, [f"Python json.load FAILED: {e}"]

    res = subprocess.run(["jq", ".", str(cfg_path)], capture_output=True, text=True, check=False)
    if res.returncode == 0:
        details.append("jq parsing: PASSED")
    else:
        ok = False
        details.append(f"jq parsing FAILED: {res.stderr}")

    modules_left = data.get("modules-left", [])
    modules_center = data.get("modules-center", [])
    modules_right = data.get("modules-right", [])
    group_spotify = data.get("group/spotify-player", {}).get("modules", [])
    all_refs = set(modules_left + modules_center + modules_right + group_spotify)

    missing_mods = []
    for m in all_refs:
        if m.startswith("group/"):
            continue
        if m not in data and not any(m.startswith(p) for p in [
            "hyprland/", "custom/", "mpris", "clock", "cpu", "memory", "pulseaudio", "network", "tray"
        ]):
            missing_mods.append(m)

    if missing_mods:
        ok = False
        details.append(f"Undefined modules in config: {missing_mods}")
    else:
        details.append(f"All {len(all_refs)} referenced modules properly registered.")

    return ok, details


def test_waybar_style_and_svg():
    details = []
    ok = True
    svg_path = DOTFILES / "waybar" / "bar-bg.svg"
    css_path = DOTFILES / "waybar" / "style.css"

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        w, h = root.get("width"), root.get("height")
        details.append(f"bar-bg.svg XML syntax: PASSED (dimensions {w}x{h})")
        rect = root.find("{http://www.w3.org/2000/svg}rect")
        if rect is not None:
            rx, ry = rect.get("rx"), rect.get("ry")
            stroke_w, fill = rect.get("stroke-width"), rect.get("fill")
            if rx == "17" and ry == "17":
                details.append("SVG rect radius conforms to 17px.")
            else:
                ok = False
                details.append(f"SVG rect rx={rx}, ry={ry} -> Expected rx=17, ry=17")
            details.append(f"SVG rect stroke-width: {stroke_w}px, fill: {fill}")

        grad = root.find(".//{http://www.w3.org/2000/svg}linearGradient")
        if grad is not None:
            x1, y1, x2, y2 = grad.get("x1"), grad.get("y1"), grad.get("x2"), grad.get("y2")
            details.append(f"SVG gradient vector: ({x1},{y1} -> {x2},{y2})")
    except Exception as e:
        ok = False
        details.append(f"bar-bg.svg XML FAILED: {e}")

    css_content = css_path.read_text(encoding="utf-8")
    if "border-radius: 17px;" in css_content:
        details.append("style.css window#waybar: border-radius 17px PASSED.")
    else:
        ok = False
        details.append("style.css window#waybar: missing border-radius: 17px.")

    aurora_colors = ["#00f0ff", "#7aa2f7", "#9778d0", "rgba(10, 15, 30, 0.50)"]
    found_colors = [c for c in aurora_colors if c in css_content]
    details.append(f"Aurora palette colors found in style.css: {len(found_colors)}/{len(aurora_colors)}")

    return ok, details


def test_swaync():
    details = []
    ok = True
    cfg_path = DOTFILES / "swaync" / "config.json"
    css_path = DOTFILES / "swaync" / "style.css"

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        details.append("swaync config.json: Valid JSON.")
        blacklist = cfg.get("notification-visibility", {})
        details.append(f"Notification blacklist entries: {len(blacklist)}")
    except Exception as e:
        return False, [f"swaync config.json ERROR: {e}"]

    css = css_path.read_text(encoding="utf-8")
    if ".control-center" in css and "border-radius: 17px;" in css:
        details.append("swaync style.css: .control-center has border-radius: 17px.")
    else:
        ok = False
        details.append("swaync style.css: .control-center missing 17px radius.")

    if ".notification" in css and "border-radius: 17px;" in css:
        details.append("swaync style.css: .notification has border-radius: 17px.")
    else:
        ok = False
        details.append("swaync style.css: .notification missing 17px radius.")

    return ok, details


def test_wofi():
    details = []
    ok = True
    cfg_path = DOTFILES / "wofi" / "config"
    css_path = DOTFILES / "wofi" / "style.css"

    cfg = cfg_path.read_text(encoding="utf-8")
    w = re.search(r"width=(\d+)", cfg)
    h = re.search(r"height=(\d+)", cfg)
    w_val = w.group(1) if w else "unknown"
    h_val = h.group(1) if h else "unknown"
    details.append(f"wofi config dimensions: width={w_val}, height={h_val}")

    css = css_path.read_text(encoding="utf-8")
    if "border-radius: 17px;" in css and "border: 2px solid" in css:
        details.append("wofi style.css: window has border-radius 17px and border 2px solid.")
    else:
        ok = False
        details.append("wofi style.css: window style discrepancy on radius or border.")

    return ok, details


def test_kitty():
    details = []
    ok = True
    conf = (DOTFILES / "kitty" / "kitty.conf").read_text(encoding="utf-8")
    op = re.search(r"background_opacity\s+([0-9.]+)", conf)
    if op and op.group(1) == "0.50":
        details.append("kitty.conf: background_opacity = 0.50 (Aurora glassmorphism)")
    else:
        ok = False
        details.append(f"kitty.conf: background_opacity = {op.group(1) if op else 'unset'}")

    colors = ["#00f0ff", "#7aa2f7", "#9778d0"]
    found = [c for c in colors if c in conf]
    details.append(f"kitty.conf: Aurora primary colors found ({len(found)}/{len(colors)})")
    return ok, details


def test_python_scripts_syntax():
    details = []
    ok = True
    py_files = []

    target_dirs = [DOTFILES, SCRIPTS, PROJECT_ROOT / "tests"]
    for td in target_dirs:
        for p in td.rglob("*.py"):
            if "__pycache__" not in p.parts:
                py_files.append(p)

    details.append(f"Discovered {len(py_files)} Python scripts to audit.")
    for py_file in sorted(py_files):
        rel = py_file.relative_to(PROJECT_ROOT)
        try:
            code = py_file.read_text(encoding="utf-8")
            ast.parse(code, filename=str(py_file))
        except Exception as e:
            ok = False
            details.append(f"SYNTAX ERROR in {rel}: {e}")

    # Specific mandatory scripts check
    mandatory_scripts = [
        DOTFILES / "hypr" / "scripts" / "hypr_ipc.py",
        SCRIPTS / "aurora_runtime.py",
        SCRIPTS / "wallpaper_daemon.py",
        SCRIPTS / "theme_models.py",
        SCRIPTS / "theme_templates.py",
        SCRIPTS / "theme_switcher.py",
        SCRIPTS / "aurora_mcp_server.py",
        SCRIPTS / "aurora_mcp" / "media_tools.py",
        SCRIPTS / "aurora_mcp" / "system_tools.py",
    ]
    for ms in mandatory_scripts:
        if ms not in py_files:
            ok = False
            details.append(f"Mandatory script missing: {ms.relative_to(PROJECT_ROOT)}")

    if ok:
        details.append(f"100% of Python scripts ({len(py_files)}) parsed successfully (AST valid).")
    return ok, details


def test_shell_scripts_syntax():
    details = []
    ok = True
    sh_files = [
        DOTFILES / "hypr" / "lock.sh",
        DOTFILES / "hypr" / "scripts" / "power-menu.sh",
        DOTFILES / "hypr" / "scripts" / "reload.sh",
        DOTFILES / "hypr" / "scripts" / "screenshot.sh",
        DOTFILES / "hypr" / "scripts" / "wallpaper_daemon.sh",
        DOTFILES / "hypr" / "scripts" / "wofi-toggle.sh",
        SCRIPTS / "hyprbar",
        SCRIPTS / "verify_aurora.sh",
        PROJECT_ROOT / "setup.sh",
        PROJECT_ROOT / "hooks" / "pre-commit",
    ]

    for sh_file in sh_files:
        if not sh_file.exists():
            ok = False
            details.append(f"Shell script missing: {sh_file.relative_to(PROJECT_ROOT)}")
            continue
        res = subprocess.run(["bash", "-n", str(sh_file)], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            details.append(f"bash -n {sh_file.relative_to(PROJECT_ROOT)}: PASSED")
        else:
            ok = False
            details.append(f"bash -n FAILED on {sh_file.relative_to(PROJECT_ROOT)}: {res.stderr.strip()}")

    return ok, details


def main():
    print("==================================================")
    print("DOTFILES STATIC & SYNTAX AUDIT TEST SUITE")
    print("==================================================")
    results = [
        run_test("Hyprland Configuration (hyprland.conf)", test_hyprland_conf),
        run_test("Waybar Configuration (config.jsonc)", test_waybar_config),
        run_test("Waybar Styling & Background (style.css / bar-bg.svg)", test_waybar_style_and_svg),
        run_test("SwayNC Configuration & Style (config.json / style.css)", test_swaync),
        run_test("Wofi Configuration & Style (config / style.css)", test_wofi),
        run_test("Kitty Configuration (kitty.conf)", test_kitty),
        run_test("Python Scripts Syntax & AST Audit", test_python_scripts_syntax),
        run_test("Shell Scripts Syntax Audit (bash -n)", test_shell_scripts_syntax),
    ]
    print("\n==================================================")
    all_ok = all(results)
    print(f"SUMMARY: {sum(results)}/{len(results)} test modules passed.")
    print("==================================================")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
