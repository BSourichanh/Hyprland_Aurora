#!/usr/bin/env python3
"""
Aurora Micro MCP Server
Model Context Protocol server for the Aurora Hyprland ecosystem.
Exposes high-level tools for Wallpaper Engine, Waybar, Spotify MPRIS,
SwayNC notifications, Audio/Volume, Session locking, Workspaces, Themes, and Dotfiles integrity.
"""

import argparse
import concurrent.futures
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from aurora_runtime import (  # noqa: E402
    get_aurora_runtime_dir,
    hypr_socket_json,
    is_aurora_proc,
    is_flock_held,
)

try:
    from aurora_mcp import media_tools, system_tools
except ImportError:
    from scripts.aurora_mcp import media_tools, system_tools


def _is_card_daemon_running() -> bool:
    """Verifies that the Spotify card daemon is actively running via flock."""
    runtime_dir = get_aurora_runtime_dir()
    return is_flock_held(runtime_dir / "spotify_card.lock") or is_flock_held(Path("/tmp/spotify_card.lock"))


def _get_wallpaper_daemon_pid() -> Optional[int]:
    """Resolves active wallpaper daemon PID verifying flock and /proc cmdline."""
    runtime_dir = get_aurora_runtime_dir()
    for lock_path in (runtime_dir / "wallpaper_daemon.lock", Path("/tmp/wallpaper_daemon.lock")):
        if not lock_path.exists() or lock_path.is_symlink():
            continue
        with contextlib.suppress(Exception):
            raw = lock_path.read_text(encoding="utf-8").strip()
            if raw.isdigit():
                pid = int(raw)
                cmd_f = Path(f"/proc/{pid}/cmdline")
                if cmd_f.exists():
                    cmdline = cmd_f.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
                    if "wallpaper_tool.py" in cmdline and (is_flock_held(lock_path) or lock_path.parent == Path("/tmp")):
                        return pid
    return None


def _read_proc_ram_and_cpu(pid: int, uptime_s: float, clk_tck: int) -> Tuple[float, float]:
    """Reads VmRSS (MiB) and lifetime CPU% from /proc/<pid>/{status,stat} without ps."""
    ram_mb = 0.0
    with contextlib.suppress(OSError, ValueError):
        with open(f"/proc/{pid}/status", "r", encoding="utf-8", errors="ignore") as f:
            for sline in f:
                if sline.startswith("VmRSS:"):
                    parts = sline.split()
                    if len(parts) >= 2:
                        ram_mb = int(parts[1]) / 1024.0
                    break
    cpu_pct = 0.0
    if uptime_s > 0.0 and clk_tck > 0:
        with contextlib.suppress(OSError, ValueError, IndexError):
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="ignore") as f:
                stat_raw = f.read()
            rparen = stat_raw.rfind(")")
            if rparen != -1:
                fields = stat_raw[rparen + 2 :].split()
                if len(fields) > 19:
                    elapsed = uptime_s - (int(fields[19]) / clk_tck)
                    if elapsed > 0.0:
                        ticks = int(fields[11]) + int(fields[12])
                        cpu_pct = max(0.0, round((ticks / clk_tck / elapsed) * 100.0, 1))
    return ram_mb, cpu_pct


def _scan_proc_status() -> Dict[str, Any]:
    """Single-pass /proc scan for aurora-wallpaper, waybar, and hyprlock."""
    uptime_s = 0.0
    with contextlib.suppress(OSError, ValueError):
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            uptime_s = float(f.read().split()[0])
    try:
        clk_tck = int(os.sysconf("SC_CLK_TCK")) or 100
    except (ValueError, OSError, AttributeError):
        clk_tck = 100

    wp_pids: List[int] = []
    waybar_pids: List[int] = []
    hyprlock_running = False
    with contextlib.suppress(OSError):
        with os.scandir("/proc") as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                with contextlib.suppress(OSError):
                    with open(f"/proc/{entry.name}/comm", "rb") as f:
                        comm = f.read().strip()
                    if comm in (b"aurora-wallpape", b"aurora-wallpaper"):
                        pid = int(entry.name)
                        if is_aurora_proc(pid):
                            wp_pids.append(pid)
                    elif comm == b"waybar":
                        waybar_pids.append(int(entry.name))
                    elif comm == b"hyprlock":
                        hyprlock_running = True

    wp_procs: List[Dict[str, Any]] = []
    total_cpu = 0.0
    total_ram = 0.0
    for pid in sorted(wp_pids):
        ram_mb, cpu_pct = _read_proc_ram_and_cpu(pid, uptime_s, clk_tck)
        total_cpu += cpu_pct
        total_ram += ram_mb
        wp_procs.append({
            "pid": pid,
            "engine": "aurora-wallpaper",
            "cpu_pct": cpu_pct,
            "ram_mb": round(ram_mb, 1),
        })
    return {
        "wp_procs": wp_procs,
        "total_cpu": total_cpu,
        "total_ram": total_ram,
        "waybar_pids": sorted(waybar_pids),
        "hyprlock_running": hyprlock_running,
    }


def get_aurora_status() -> Dict[str, Any]:
    """
    Returns an exhaustive real-time diagnostic of the Aurora desktop ecosystem:
    - Wallpaper Engine (PIDs validated via unified /proc scan, CPU/RAM, daemon state)
    - Wayland Layers per monitor (Background, Bottom, Top, Overlay)
    - Waybar status and PID
    - GPU usage (Intel DRM engine telemetry)
    - Audio status (Volume, Sink/Source mute via PipeWire)
    - SwayNC notifications (Count, DND mode)
    - Spotify MPRIS status, track details, and progress
    - Session lock state (/proc comm, flock instance, runtime flag)
    - Workspaces distribution across monitors
    - Dotfiles hard links integrity (42/42 canonical check)
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        fut_swaync = executor.submit(media_tools._get_swaync_info)
        fut_audio = executor.submit(media_tools._get_audio_info)
        fut_spotify = executor.submit(media_tools._get_spotify_info)
        fut_hardlinks = executor.submit(system_tools._check_hardlinks_dict)

        daemon_pid = _get_wallpaper_daemon_pid()
        proc_snap = _scan_proc_status()
        layers_raw = hypr_socket_json("j/layers", timeout=1.0)
        monitors_raw = hypr_socket_json("j/monitors", timeout=1.0)
        workspaces_raw = hypr_socket_json("j/workspaces", timeout=1.0)
        gpu_info = system_tools._get_gpu_info()
        lock_info = system_tools._get_lock_info(hyprlock_running=proc_snap["hyprlock_running"])
        card_daemon_running = _is_card_daemon_running()

        swaync_info = fut_swaync.result()
        audio_info = fut_audio.result()
        spotify_info = fut_spotify.result()
        hardlinks_info = fut_hardlinks.result()

    layers_data = layers_raw if isinstance(layers_raw, dict) else {}
    layer_summary = {}
    for mon, mdata in layers_data.items():
        if not isinstance(mdata, dict):
            continue
        lvl_map = {}
        for lvl_id, items in mdata.get("levels", {}).items():
            lvl_name = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}.get(str(lvl_id), f"Lvl{lvl_id}")
            lvl_map[lvl_name] = [f"{it.get('namespace', '?')}[pid:{it.get('pid', '?')}]" for it in items]
        layer_summary[mon] = lvl_map

    monitors_data = monitors_raw if isinstance(monitors_raw, list) else []
    workspaces_data = workspaces_raw if isinstance(workspaces_raw, list) else []
    mon_summary = []
    for m in monitors_data:
        if not isinstance(m, dict):
            continue
        mname = m.get("name")
        mon_summary.append({
            "name": mname,
            "focused": m.get("focused", False),
            "active_workspace": m.get("activeWorkspace", {}).get("id"),
            "workspaces": [w.get("id") for w in workspaces_data if isinstance(w, dict) and w.get("monitor") == mname],
        })

    wp_procs = proc_snap["wp_procs"]
    waybar_pids = proc_snap["waybar_pids"]

    return {
        "wallpaper_engine": {
            "mode": "native-egl",
            "daemon_pid": daemon_pid,
            "process_count": len(wp_procs),
            "processes": wp_procs,
            "total_cpu_pct": round(proc_snap["total_cpu"], 1),
            "total_ram_mb": round(proc_snap["total_ram"], 1),
        },
        "waybar": {
            "running": len(waybar_pids) > 0,
            "pids": waybar_pids,
        },
        "gpu": gpu_info,
        "swaync": swaync_info,
        "audio": audio_info,
        "lock": lock_info,
        "spotify": spotify_info,
        "spotify_card_daemon": {
            "running": card_daemon_running,
            "endpoint": "http://127.0.0.1:8975/events" if card_daemon_running else None,
        },
        "monitors": mon_summary,
        "layers": layer_summary,
        "hardlinks": hardlinks_info,
    }


def _create_mcp_server():
    """Creates and registers tools on FastMCP lazily so --help works without mcp."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("aurora-mcp")
    server.tool()(get_aurora_status)
    server.tool()(system_tools.manage_wallpaper)
    server.tool()(system_tools.manage_hyprbar)
    server.tool()(system_tools.lock_session)
    server.tool()(system_tools.reload_all)
    server.tool()(system_tools.audit_hardlinks)
    server.tool()(system_tools.wofi_launch)
    server.tool()(system_tools.compact_workspaces)
    server.tool()(system_tools.switch_theme)
    server.tool()(media_tools.manage_swaync)
    server.tool()(media_tools.manage_blacklist)
    server.tool()(media_tools.audio_control)
    server.tool()(media_tools.spotify_control)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Aurora Micro MCP Server & Diagnostic CLI")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "status", "audit", "reload"],
        help="Action CLI ou 'serve' (défaut) pour démarrer le serveur MCP stdio",
    )
    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(get_aurora_status(), indent=2, ensure_ascii=False))
    elif args.command == "audit":
        print(json.dumps(system_tools.audit_hardlinks(), indent=2, ensure_ascii=False))
    elif args.command == "reload":
        print(json.dumps(system_tools.reload_all(), indent=2, ensure_ascii=False))
    else:
        mcp = _create_mcp_server()
        mcp.run()


if __name__ == "__main__":
    main()
