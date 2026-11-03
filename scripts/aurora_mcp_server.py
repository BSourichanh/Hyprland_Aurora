#!/usr/bin/env python3
"""
Aurora Micro MCP Server
Model Context Protocol server for the Aurora Hyprland ecosystem.
Exposes high-level tools for Wallpaper Engine, Waybar, Spotify MPRIS,
SwayNC notifications, Audio/Volume, Session locking, Workspaces, and Dotfiles integrity.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

# Configuration des chemins
PROJECT_DIR = Path(__file__).resolve().parent.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"

# Import des modules modulaires Aurora MCP
try:
    from aurora_mcp import media_tools, system_tools
except ImportError:
    from scripts.aurora_mcp import media_tools, system_tools

mcp = FastMCP("aurora-mcp")


# ============================================================================
# DIAGNOSTIC GLOBAL (ORCHESTRATEUR STATUS)
# ============================================================================

@mcp.tool()
def get_aurora_status() -> Dict[str, Any]:
    """
    Returns an exhaustive real-time diagnostic of the Aurora desktop ecosystem:
    - Wallpaper Engine (PIDs, CPU/RAM, active renderer GPU/CPU, daemon state)
    - Wayland Layers per monitor (Background, Bottom, Top, Overlay)
    - Waybar status and PID
    - GPU usage (Intel DRM engine telemetry)
    - Audio status (Volume, Sink/Source mute via PipeWire)
    - SwayNC notifications (Count, DND mode)
    - Spotify MPRIS status, track details, and progress
    - Session lock state (flag, Hyprlock layer)
    - Workspaces distribution across DP-1 and DP-2
    - Dotfiles hard links integrity (37/37 check)
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
        pg_res = subprocess.run(["pgrep", "-f", "aurora-wallpaper"], capture_output=True, text=True)
        if pg_res.returncode == 0:
            for line in pg_res.stdout.strip().splitlines():
                if line and line.isdigit():
                    pid = int(line)
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
                        "engine": "aurora-wallpaper",
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
    layers_data = system_tools._run_hyprctl(["layers"]) or {}
    layer_summary = {}
    for mon, mdata in layers_data.items():
        lvl_map = {}
        for lvl_id, items in mdata.get("levels", {}).items():
            lvl_name = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}.get(str(lvl_id), f"Lvl{lvl_id}")
            lvl_map[lvl_name] = [f"{it.get('namespace', '?')}[pid:{it.get('pid', '?')}]" for it in items]
        layer_summary[mon] = lvl_map

    # 4. Monitors & Workspaces
    monitors_data = system_tools._run_hyprctl(["monitors"]) or []
    workspaces_data = system_tools._run_hyprctl(["workspaces"]) or []
    mon_summary = []
    for m in monitors_data:
        mname = m.get("name")
        mon_summary.append({
            "name": mname,
            "focused": m.get("focused", False),
            "active_workspace": m.get("activeWorkspace", {}).get("id"),
            "workspaces": [w.get("id") for w in workspaces_data if w.get("monitor") == mname]
        })

    # 5. Telemetry & Subsystems
    spotify_info = media_tools._get_spotify_info()
    gpu_info = system_tools._get_gpu_info()
    swaync_info = media_tools._get_swaync_info()
    audio_info = media_tools._get_audio_info()
    lock_info = system_tools._get_lock_info()

    card_daemon_running = Path("/tmp/spotify_card.lock").exists()

    # 6. Hard links (audit dotfiles <-> ~/.config)
    links_audit = system_tools._check_hardlinks_dict()

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
        "gpu": gpu_info,
        "swaync": swaync_info,
        "audio": audio_info,
        "lock": lock_info,
        "spotify": spotify_info,
        "spotify_card_daemon": {
            "running": card_daemon_running,
            "endpoint": "http://127.0.0.1:8975/events" if card_daemon_running else None
        },
        "monitors": mon_summary,
        "layers": layer_summary,
        "hardlinks": links_audit
    }


# ============================================================================
# ENREGISTREMENT DES OUTILS MODULAIRES SUR FastMCP
# ============================================================================

# Outils Système & Fenêtrage
mcp.tool()(system_tools.manage_wallpaper)
mcp.tool()(system_tools.manage_hyprbar)
mcp.tool()(system_tools.lock_session)
mcp.tool()(system_tools.reload_all)
mcp.tool()(system_tools.audit_hardlinks)
mcp.tool()(system_tools.wofi_launch)
mcp.tool()(system_tools.compact_workspaces)

# Outils Médias & Notifications
mcp.tool()(media_tools.manage_swaync)
mcp.tool()(media_tools.manage_blacklist)
mcp.tool()(media_tools.audio_control)
mcp.tool()(media_tools.spotify_control)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(get_aurora_status(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "audit":
        print(json.dumps(system_tools.audit_hardlinks(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "reload":
        print(json.dumps(system_tools.reload_all(), indent=2, ensure_ascii=False))
    else:
        mcp.run()
