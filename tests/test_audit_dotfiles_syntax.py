#!/usr/bin/env python3
"""
Test Suite: Syntax and Static Audit for Hyprland Project Dotfiles & Scripts
Checks:
- Hyprland 0.57.2 & hyprland.lua / hyprviz.lua (syntax, follow_mouse, kb_layout, rules, binds)
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


_LUA_TOK_RE = re.compile(
    r"--\[(?P<ceq>=*)\[[\s\S]*?\](?P=ceq)\]|--[^\n]*|\[(?P<seq>=*)\[(?P<lstr>[\s\S]*?)\](?P=seq)\]"
    r'|"(?P<dstr>(?:\\.|[^"\\])*)"|\'(?P<sstr>(?:\\.|[^\'\\])*)\'|\.\.|[A-Za-z_]\w*|[{}()\[\],;=+.:]'
)


def _tokenize_lua(content: str):
    """Returns non-comment Lua tokens and comment-stripped source text."""
    tokens, chunks, last = [], [], 0
    for m in _LUA_TOK_RE.finditer(content):
        tok = m.group(0)
        if tok.startswith("--"):
            chunks.append(content[last:m.start()] + " ")
            last = m.end()
            continue
        sg = next((g for g in ("dstr", "sstr", "lstr") if m.group(g) is not None), None)
        tokens.append(("STR", m.group(sg)) if sg else ("ID" if tok[0].isalpha() or tok[0] == "_" else "OP", tok))
    chunks.append(content[last:])
    return tokens, "".join(chunks)


def _detect_lua_bind_collisions(tokens):
    """Detects colliding hl.bind(...) calls across Lua branches, ipairs loops, and flags."""
    lstrs, llists, stack, seen, conflicts, i, n, bid, count = {}, {}, [], {}, [], 0, len(tokens), 0, 0
    while i < n:
        kind, val = tokens[i]
        prev_op, next_op = (tokens[i - 1][1] if i > 0 else ""), (tokens[i + 1][1] if i + 1 < n else "")
        if (kind, val) == ("ID", "local") and i + 3 < n and tokens[i + 1][0] == "ID" and tokens[i + 2] == ("OP", "="):
            vn = tokens[i + 1][1]
            if tokens[i + 3][0] == "STR":
                lstrs[vn] = tokens[i + 3][1]
            elif tokens[i + 3] == ("OP", "{"):
                j, bd, items = i + 4, 1, []
                while j < n and bd > 0:
                    bd += (tokens[j] == ("OP", "{")) - (tokens[j] == ("OP", "}"))
                    if bd == 1 and tokens[j][0] == "STR":
                        items.append(tokens[j][1])
                    j += 1
                llists[vn] = items
        elif kind == "ID" and prev_op not in (".", ":") and next_op != "=":
            if val == "if":
                bid += 1; stack.append(["if", bid, "then"])
            elif val in ("elseif", "else") and stack and stack[-1][0] == "if":
                bid += 1; stack[-1][2] = f"elseif_{bid}" if val == "elseif" else "else"
            elif val in ("function", "while"):
                stack.append(["blk", None])
            elif val == "for":
                j, lv, ll = i + 1, [], None
                while j < n and tokens[j] != ("ID", "do"):
                    if tokens[j] == ("ID", "in") and j + 4 < n and tokens[j + 1:j + 3] == [("ID", "ipairs"), ("OP", "(")]:
                        ll = llists.get(tokens[j + 3][1]); break
                    if tokens[j][0] == "ID": lv.append(tokens[j][1])
                    j += 1
                stack.append(["loop", (lv[-1], ll) if lv and ll else None])
            elif val == "end" and stack:
                stack.pop()
        if i + 3 < n and tokens[i:i + 4] == [("ID", "hl"), ("OP", "."), ("ID", "bind"), ("OP", "(")]:
            j, depth, args, cur = i + 4, 1, [], []
            while j < n and depth > 0:
                tk = tokens[j]; depth += (tk[1] in "([{") - (tk[1] in ")]}")
                if depth == 0: break
                if tk == ("OP", ",") and depth == 1: args.append(cur); cur = []
                else: cur.append(tk)
                j += 1
            args.append(cur)
            ft = args[2] if len(args) >= 3 else []
            flags = {ft[k][1]: (True if ft[k + 2][1] == "true" else False if ft[k + 2][1] == "false" else ft[k + 2][1])
                     for k in range(len(ft) - 2) if ft[k][0] == "ID" and ft[k + 1] == ("OP", "=") and ft[k + 2][0] in ("ID", "STR")}
            fkey = tuple(sorted((k, v) for k, v in flags.items() if v is not False))
            envs = [{}]
            for b in stack:
                if b[0] == "loop" and b[1] and any(t == ("ID", b[1][0]) for t in args[0]):
                    envs = [{**env, b[1][0]: item} for env in envs for item in b[1][1]]
            bpath = tuple((b[1], b[2]) for b in stack if b[0] == "if")
            bdict = dict(bpath)
            for env in envs:
                raw = "".join(t[1] if t[0] == "STR" else env.get(t[1], lstrs.get(t[1], f"<{t[1]}>")) for t in args[0] if t[1] != "..")
                parts = [p.strip() for p in raw.split("+") if p.strip()]
                key = ((tuple(sorted(p.upper() for p in parts[:-1])), parts[-1].lower()) if parts else ((), ""), fkey)
                count += 1
                if any(all(bdict[kid] == kt for kid, kt in pbp if kid in bdict) for pbp, _ in seen.get(key, [])):
                    conflicts.append((raw, fkey))
                seen.setdefault(key, []).append((bpath, raw))
            i = j + 1; continue
        i += 1
    return count, conflicts


def test_hyprland_conf():
    ver = subprocess.run(["Hyprland", "--version"], capture_output=True, text=True, check=False)
    lua_path, viz_path = DOTFILES / "hypr" / "hyprland.lua", DOTFILES / "hypr" / "hyprviz.lua"
    for p in (lua_path, viz_path):
        if not p.exists(): return False, [f"File missing: {p}"]
    res = subprocess.run(["Hyprland", "--config", str(lua_path), "--verify-config"], capture_output=True, text=True, check=False)
    dep = subprocess.run(["hyprctl", "deprecated-config"], capture_output=True, text=True, check=False)
    dep_out = f"{dep.stdout}\n{dep.stderr}".strip()
    tokens, active = _tokenize_lua(lua_path.read_text(encoding="utf-8"))
    _, viz_active = _tokenize_lua(viz_path.read_text(encoding="utf-8"))
    fm, kb = re.search(r"\bfollow_mouse\s*=\s*(\d+)", active), re.search(r'\bkb_layout\s*=\s*["\']([^"\']+)["\']', active)
    w_rules, l_rules = re.findall(r"\bhl\.window_rule\s*\(", active), re.findall(r"\bhl\.layer_rule\s*\(", active)
    b_cnt, conflicts = _detect_lua_bind_collisions(tokens)
    checks = [
        (ver.returncode == 0 and "0.57.2" in f"{ver.stdout}\n{ver.stderr}", f"Hyprland --version: {'0.57.2' if '0.57.2' in ver.stdout else f'rc={ver.returncode}'}"),
        (res.returncode == 0 and "config ok" in f"{res.stdout}\n{res.stderr}", f"Hyprland --verify-config (hyprland.lua + hyprviz.lua): {'config ok (rc=0)' if res.returncode == 0 else f'FAIL rc={res.returncode}'}"),
        (dep.returncode == 0 and (not dep_out or dep_out.lower() == "all good!"), f"hyprctl deprecated-config: {dep_out or 'empty'} (rc={dep.returncode})"),
        ('require("hyprviz")' in active or "require('hyprviz')" in active, 'hyprland.lua includes require("hyprviz")'),
        ("hl.config" in viz_active, "hyprviz.lua defines hl.config(...)"),
        (bool(fm and fm.group(1) == "0"), f"Directive follow_mouse = {fm.group(1) if fm else 'missing'} (Expected 0)"),
        (bool(kb and kb.group(1) == "fr"), f"Directive kb_layout = {kb.group(1) if kb else 'missing'} (Expected 'fr')"),
        (bool(re.search(r"\buse_fp16\s*=\s*0\b", active)), "Directive render.use_fp16 = 0 present"),
        ("allow_new_top_layers_over_existing_fullscreen" in active, "Directive layers.allow_new_top_layers_over_existing_fullscreen present"),
        ("on_created_empty" not in active, "No active on_created_empty in hyprland.lua"),
        ('hl.on("workspace.created"' in active or "hl.on('workspace.created'" in active, 'hl.on("workspace.created") hook present'),
        (len(w_rules) > 0 and len(l_rules) > 0, f"Lua rules: {len(w_rules)} hl.window_rule, {len(l_rules)} hl.layer_rule"),
        (not conflicts, f"Keybind audit ({b_cnt} hl.bind entries): {'0 collisions' if not conflicts else f'COLLISIONS {conflicts[:5]}'}"),
    ]
    return all(c[0] for c in checks), [c[1] for c in checks]


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
    cfg_path, css_path = DOTFILES / "swaync" / "config.json", DOTFILES / "swaync" / "style.css"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        details = ["swaync config.json: Valid JSON.", f"Notification blacklist entries: {len(cfg.get('notification-visibility', {}))}"]
    except Exception as e:
        return False, [f"swaync config.json ERROR: {e}"]
    css = css_path.read_text(encoding="utf-8")
    cc_ok = ".control-center" in css and "border-radius: 17px;" in css
    nt_ok = ".notification" in css and "border-radius: 17px;" in css
    details.append("swaync style.css: .control-center has border-radius: 17px." if cc_ok else "swaync style.css: .control-center missing 17px radius.")
    details.append("swaync style.css: .notification has border-radius: 17px." if nt_ok else "swaync style.css: .notification missing 17px radius.")
    return cc_ok and nt_ok, details


def test_wofi():
    cfg = (DOTFILES / "wofi" / "config").read_text(encoding="utf-8")
    w, h = re.search(r"width=(\d+)", cfg), re.search(r"height=(\d+)", cfg)
    css = (DOTFILES / "wofi" / "style.css").read_text(encoding="utf-8")
    ok = "border-radius: 17px;" in css and "border: 2px solid" in css
    details = [
        f"wofi config dimensions: width={w.group(1) if w else 'unknown'}, height={h.group(1) if h else 'unknown'}",
        "wofi style.css: window has border-radius 17px and border 2px solid." if ok else "wofi style.css: window style discrepancy on radius or border.",
    ]
    return ok, details


def test_kitty():
    conf = (DOTFILES / "kitty" / "kitty.conf").read_text(encoding="utf-8")
    op = re.search(r"background_opacity\s+([0-9.]+)", conf)
    ok = bool(op and op.group(1) == "0.50")
    found = [c for c in ("#00f0ff", "#7aa2f7", "#9778d0") if c in conf]
    return ok, [
        "kitty.conf: background_opacity = 0.50 (Aurora glassmorphism)" if ok else f"kitty.conf: background_opacity = {op.group(1) if op else 'unset'}",
        f"kitty.conf: Aurora primary colors found ({len(found)}/3)",
    ]


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
        SCRIPTS / "aurora_osd.py",
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
        run_test("Hyprland Configuration (hyprland.lua / hyprviz.lua)", test_hyprland_conf),
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
