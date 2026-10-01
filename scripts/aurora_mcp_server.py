#!/usr/bin/env python3
"""
Aurora Micro MCP Server
Model Context Protocol server for the Aurora Hyprland ecosystem.
Exposes high-level tools for Wallpaper Engine, Waybar, Spotify MPRIS,
Wofi launcher, Workspaces, and Dotfiles integrity.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

PROJECT_DIR = Path(__file__).resolve().parent.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
SCRIPTS_DIR = PROJECT_DIR / "scripts"
WALLPAPER_TOOL = SCRIPTS_DIR / "wallpaper_tool.py"
HYPRBAR_TOOL = SCRIPTS_DIR / "hyprbar"

mcp = FastMCP("aurora-mcp")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _run_hyprctl(args: List[str]) -> Any:
    """Executes hyprctl with JSON flag."""
    try:
        res = subprocess.run(["hyprctl", "-j", *args], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    return None


def _check_hardlinks_dict() -> Dict[str, Any]:
    """Audits the hard links between dotfiles/ and ~/.config/."""
    mismatches = []
    missing = []
    checked = 0

    for root, _, files in os.walk(DOTFILES_DIR):
        for f in files:
            if f.endswith((".bak", "-bak", ".pyc", ".so")):
                continue
            dot_path = Path(root) / f
            rel = str(dot_path.relative_to(DOTFILES_DIR))
            conf_path = CONFIG_DIR / rel

            if not conf_path.exists():
                missing.append(rel)
                continue

            checked += 1
            try:
                if dot_path.stat().st_ino != conf_path.stat().st_ino:
                    mismatches.append(rel)
            except Exception:
                missing.append(rel)

    return {
        "total_checked": checked,
        "missing": missing,
        "mismatches": mismatches,
        "all_ok": len(mismatches) == 0 and len(missing) == 0
    }


def _get_spotify_info() -> Dict[str, Any]:
    """Retrieves current Spotify playback information via MPRIS."""
    info = {"status": "Stopped", "track": "", "artist": "", "album": "", "position": "", "running": False}
    try:
        status_res = subprocess.run(["playerctl", "--player=spotify", "status"], capture_output=True, text=True, timeout=2)
        if status_res.returncode == 0:
            info["status"] = status_res.stdout.strip()
            info["running"] = True
            
            meta_res = subprocess.run(
                ["playerctl", "--player=spotify", "metadata", "--format", "{{artist}} - {{title}}||{{album}}||{{position}}||{{mpris:length}}"],
                capture_output=True, text=True, timeout=2
            )
            if meta_res.returncode == 0 and "||" in meta_res.stdout:
                parts = meta_res.stdout.strip().split("||")
                track_str = parts[0]
                if " - " in track_str:
                    info["artist"], info["track"] = track_str.split(" - ", 1)
                else:
                    info["track"] = track_str
                if len(parts) > 1:
                    info["album"] = parts[1]
                if len(parts) > 3 and parts[2] and parts[3]:
                    try:
                        pos_s = int(parts[2]) // 1000000
                        len_s = int(parts[3]) // 1000000
                        info["position"] = f"{pos_s // 60:02d}:{pos_s % 60:02d} / {len_s // 60:02d}:{len_s % 60:02d}"
                    except Exception:
                        pass
    except Exception:
        pass
    return info


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
def get_aurora_status() -> Dict[str, Any]:
    """
    Returns an exhaustive real-time diagnostic of the Aurora desktop ecosystem:
    - Wallpaper Engine (PIDs, CPU/RAM, active renderer GPU/CPU, daemon state)
    - Wayland Layers per monitor (Background, Bottom, Top, Overlay)
    - Waybar status and PID
    - Spotify MPRIS status, track details, and progress
    - Workspaces distribution across DP-1 and DP-2
    - Dotfiles hard links integrity (29/29 check)
    """
    # 1. Wallpaper engine status
    wp_cfg_path = DOTFILES_DIR / "hypr" / "wallpaper_renderer.json"
    wp_mode = "gpu"
    if wp_cfg_path.exists():
        try:
            wp_mode = json.loads(wp_cfg_path.read_text()).get("renderer", "gpu")
        except Exception:
            pass

    daemon_pid = None
    lock_file = Path("/tmp/wallpaper_daemon.lock")
    if lock_file.exists():
        try:
            daemon_pid = int(lock_file.read_text().strip())
        except Exception:
            pass

    wp_procs = []
    total_cpu = 0.0
    total_ram = 0.0
    try:
        pg_res = subprocess.run(["pgrep", "-f", "linux-wallpaperengine"], capture_output=True, text=True)
        if pg_res.returncode == 0:
            for line in pg_res.stdout.strip().splitlines():
                if line:
                    pid = int(line)
                    cmdline_f = Path(f"/proc/{pid}/cmdline")
                    screen = "unknown"
                    if cmdline_f.exists():
                        args = cmdline_f.read_bytes().split(b"\x00")
                        for idx, arg in enumerate(args):
                            if arg == b"--screen-root" and idx + 1 < len(args):
                                screen = args[idx + 1].decode("utf-8", errors="ignore")
                    
                    # RAM & CPU
                    ram_mb = 0.0
                    stat_f = Path(f"/proc/{pid}/status")
                    if stat_f.exists():
                        for sline in stat_f.read_text().splitlines():
                            if sline.startswith("VmRSS:"):
                                ram_mb = int(sline.split()[1]) / 1024
                                break
                    
                    cpu_pct = 0.0
                    ps_res = subprocess.run(["ps", "-p", str(pid), "-o", "%cpu", "--no-headers"], capture_output=True, text=True)
                    if ps_res.returncode == 0 and ps_res.stdout.strip():
                        try:
                            cpu_pct = float(ps_res.stdout.strip().replace(",", "."))
                        except Exception:
                            pass
                    
                    total_cpu += cpu_pct
                    total_ram += ram_mb
                    wp_procs.append({
                        "pid": pid,
                        "screen": screen,
                        "cpu_pct": cpu_pct,
                        "ram_mb": round(ram_mb, 1)
                    })
    except Exception:
        pass

    # 2. Waybar status
    waybar_pids = []
    wb_res = subprocess.run(["pgrep", "-x", "waybar"], capture_output=True, text=True)
    if wb_res.returncode == 0:
        waybar_pids = [int(p) for p in wb_res.stdout.strip().splitlines() if p]

    # 3. Wayland Layers
    layers_data = _run_hyprctl(["layers"]) or {}
    layer_summary = {}
    for mon, mdata in layers_data.items():
        lvl_map = {}
        for lvl_id, items in mdata.get("levels", {}).items():
            lvl_name = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}.get(str(lvl_id), f"Lvl{lvl_id}")
            lvl_map[lvl_name] = [f"{it.get('namespace', '?')}[pid:{it.get('pid', '?')}]" for it in items]
        layer_summary[mon] = lvl_map

    # 4. Monitors & Workspaces
    monitors_data = _run_hyprctl(["monitors"]) or []
    workspaces_data = _run_hyprctl(["workspaces"]) or []
    mon_summary = []
    for m in monitors_data:
        mname = m.get("name")
        mon_summary.append({
            "name": mname,
            "focused": m.get("focused", False),
            "active_workspace": m.get("activeWorkspace", {}).get("id"),
            "workspaces": [w.get("id") for w in workspaces_data if w.get("monitor") == mname]
        })

    # 5. Spotify & Card Daemon
    spotify_info = _get_spotify_info()
    card_daemon_running = False
    card_lock = Path("/tmp/spotify_card.lock")
    if card_lock.exists():
        card_daemon_running = True

    # 6. Hard links
    links_audit = _check_hardlinks_dict()

    return {
        "wallpaper_engine": {
            "mode": wp_mode,
            "daemon_pid": daemon_pid,
            "process_count": len(wp_procs),
            "processes": wp_procs,
            "total_cpu_pct": round(total_cpu, 1),
            "total_ram_mb": round(total_ram, 1)
        },
        "waybar": {
            "running": len(waybar_pids) > 0,
            "pids": waybar_pids
        },
        "spotify": spotify_info,
        "spotify_card_daemon": {
            "running": card_daemon_running,
            "endpoint": "http://127.0.0.1:8975/events" if card_daemon_running else None
        },
        "monitors": mon_summary,
        "layers": layer_summary,
        "hardlinks": links_audit
    }


@mcp.tool()
def manage_wallpaper(action: str, screen: Optional[str] = None) -> Dict[str, Any]:
    """
    Manages Wallpaper Engine (Lucy) processes and renderer.
    - action: 'status', 'restart', 'ensure', 'renderer_gpu', 'renderer_cpu', 'mask', 'sync'
    - screen: optional monitor target ('DP-1' or 'DP-2') for 'ensure' or 'restart'
    """
    cmd = [sys.executable, str(WALLPAPER_TOOL)]
    if action == "status":
        cmd.append("status")
    elif action == "restart":
        cmd.append("restart")
        if screen:
            cmd.extend(["--screen", screen])
    elif action == "ensure":
        cmd.append("ensure")
        if screen:
            cmd.extend(["--screen", screen])
    elif action == "renderer_gpu":
        cmd.extend(["renderer", "gpu"])
    elif action == "renderer_cpu":
        cmd.extend(["renderer", "cpu"])
    elif action == "mask":
        cmd.append("mask")
    elif action == "sync":
        cmd.append("sync")
    else:
        return {"ok": False, "error": f"Action inconnue: {action}"}

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return {
        "ok": res.returncode == 0,
        "action": action,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }


@mcp.tool()
def manage_hyprbar(action: str) -> Dict[str, Any]:
    """
    Controls Waybar and the Spotify ecosystem via hyprbar CLI.
    - action: 'restart' (full restart), 'reload' (CSS reload), 'toggle' (hide/show), 'status'
    """
    if action not in ("restart", "reload", "toggle", "status"):
        return {"ok": False, "error": f"Action non valide: {action}. Utiliser 'restart', 'reload', 'toggle' ou 'status'."}

    res = subprocess.run([str(HYPRBAR_TOOL), action], capture_output=True, text=True, timeout=10)
    return {
        "ok": res.returncode == 0,
        "action": action,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }


@mcp.tool()
def audit_hardlinks() -> Dict[str, Any]:
    """
    Audits the integrity of the 29 hard links between dotfiles/ and ~/.config/.
    Ensures that modifications are directly reflected across inodes without broken links.
    """
    return _check_hardlinks_dict()


@mcp.tool()
def spotify_control(command: str) -> Dict[str, Any]:
    """
    Controls Spotify playback via MPRIS D-Bus.
    - command: 'play_pause', 'next', 'previous', 'status'
    """
    cmd_map = {
        "play_pause": "play-pause",
        "next": "next",
        "previous": "previous",
        "status": "status"
    }
    sub = cmd_map.get(command)
    if not sub:
        return {"ok": False, "error": f"Commande Spotify inconnue: {command}"}

    if command == "status":
        return {"ok": True, "spotify": _get_spotify_info()}

    res = subprocess.run(["playerctl", "--player=spotify", sub], capture_output=True, text=True, timeout=3)
    time.sleep(0.15)
    return {
        "ok": res.returncode == 0,
        "command": command,
        "spotify": _get_spotify_info()
    }


@mcp.tool()
def wofi_launch(mode: str = "drun") -> Dict[str, Any]:
    """
    Launches Wofi in 'drun' (applications) or 'power' (power menu) mode.
    Runs asynchronously without blocking.
    """
    if mode == "power":
        script = DOTFILES_DIR / "hypr" / "scripts" / "power-menu.sh"
        subprocess.Popen(["bash", str(script)])
        return {"ok": True, "mode": "power", "message": "Menu power lancé"}
    elif mode == "drun":
        subprocess.Popen(["wofi", "--show", "drun"])
        return {"ok": True, "mode": "drun", "message": "Lanceur d'applications Wofi lancé"}
    else:
        return {"ok": False, "error": f"Mode Wofi non supporté: {mode}"}


@mcp.tool()
def compact_workspaces() -> Dict[str, Any]:
    """
    Triggers deterministic auto-compacting of workspaces across DP-1 and DP-2.
    Ensures bounds (DP-2: 1-5, DP-1: 6-10) without ghost gaps.
    """
    compact_script = DOTFILES_DIR / "hypr" / "scripts" / "workspace-autocompact.py"
    if not compact_script.exists():
        return {"ok": False, "error": "Script workspace-autocompact.py introuvable"}

    res = subprocess.run([sys.executable, str(compact_script)], capture_output=True, text=True, timeout=5)
    return {
        "ok": res.returncode == 0,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(get_aurora_status(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "audit":
        print(json.dumps(audit_hardlinks(), indent=2, ensure_ascii=False))
    else:
        # Standard MCP stdio server execution
        mcp.run()
