#!/usr/bin/env python3
"""
Hyprland Dynamic Workspace Auto-Compactor
Compacts workspace numbering dynamically per monitor to eliminate gaps.
- DP-2 (left monitor): Base workspace 1 (1..5)
- DP-1 (right monitor): Base workspace 6 (6..10)
Overflow workspaces (> max) never spill onto another monitor's pool.
"""

import fcntl
import json
import os
from pathlib import Path
import select
import signal
import socket
import sys
import time
from typing import Dict, List, Optional, Set

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hypr_ipc import (
    get_aurora_runtime_dir,
    get_hypr_sockets,
    hypr_batch,
    hypr_json,
    is_session_locked,
)

LOCK_FILE = str(get_aurora_runtime_dir() / "autocompact.lock")
_MONITOR_CONFIGS_CACHE: Optional[Dict[str, Dict[str, int]]] = None


def get_monitor_configs(force_refresh: bool = False) -> Dict[str, Dict[str, int]]:
    global _MONITOR_CONFIGS_CACHE
    if not force_refresh and _MONITOR_CONFIGS_CACHE is not None:
        return _MONITOR_CONFIGS_CACHE
    if force_refresh:
        _MONITOR_CONFIGS_CACHE = None

    rules = hypr_json("j/workspacerules")
    mon_workspaces: Dict[str, List[int]] = {}
    if isinstance(rules, list):
        for r in rules:
            ws_str = str(r.get("workspaceString", ""))
            mon = r.get("monitor", "")
            if ws_str.isdigit() and mon:
                ws_id = int(ws_str)
                if ws_id < 90:
                    mon_workspaces.setdefault(mon, []).append(ws_id)

    configs: Dict[str, Dict[str, int]] = {
        "DP-2": {"base": 1, "max": 5},
        "DP-1": {"base": 6, "max": 10},
    }
    for mon, ids in mon_workspaces.items():
        if ids:
            configs[mon] = {"base": min(ids), "max": max(ids)}
    if isinstance(rules, list) and len(rules) > 0:
        _MONITOR_CONFIGS_CACHE = configs
    return configs


def _build_targets(count: int, base: int, max_ws: int, global_bound: Set[int],
                   other_occupied: Set[int], max_pool_ws: int) -> List[int]:
    """Builds compact target workspace IDs strictly respecting cfg['max'] and monitor boundaries."""
    targets: List[int] = []
    cand = base
    while len(targets) < count:
        if cand <= max_ws:
            targets.append(cand)
        else:
            if cand <= max_pool_ws:
                cand = max_pool_ws + 1
            while cand in global_bound or cand in other_occupied or (90 <= cand <= 99):
                cand += 1
            targets.append(cand)
        cand += 1
    return targets


def compact_workspaces() -> bool:
    if is_session_locked():
        return False

    configs = get_monitor_configs()
    monitors = hypr_json("j/monitors")
    clients = hypr_json("j/clients")
    workspaces = hypr_json("j/workspaces")

    if not monitors or not isinstance(monitors, list):
        return False

    focused_mon = None
    mon_info_map = {}
    for m in monitors:
        mon_name = m.get("name")
        if mon_name:
            mon_info_map[mon_name] = m
            if m.get("focused"):
                focused_mon = mon_name

    ws_mon_map = {}
    if isinstance(workspaces, list):
        for ws in workspaces:
            ws_id = ws.get("id")
            ws_mon = ws.get("monitor")
            if ws_id is not None and ws_mon:
                ws_mon_map[ws_id] = ws_mon

    def get_ws_monitor(ws_id: int) -> str:
        for m_name, cfg in configs.items():
            if cfg["base"] <= ws_id <= cfg["max"]:
                return m_name
        if ws_id in ws_mon_map:
            return ws_mon_map[ws_id]
        return "DP-1" if ws_id >= 6 else "DP-2"

    occupied: Dict[str, Dict[int, List[str]]] = {m_name: {} for m_name in configs.keys()}
    if isinstance(clients, list):
        for c in clients:
            if not c.get("mapped") or c.get("pinned"):
                continue
            ws_id = c.get("workspace", {}).get("id")
            addr = c.get("address")
            if ws_id is None or ws_id < 1 or ws_id >= 90 or not addr:
                continue
            m_name = get_ws_monitor(ws_id)
            if m_name in occupied:
                occupied[m_name].setdefault(ws_id, []).append(addr)

    max_pool_ws = max(cfg["max"] for cfg in configs.values())
    all_dispatches: List[str] = []

    for m_name, cfg in configs.items():
        if m_name not in mon_info_map:
            continue
        base, max_ws = cfg["base"], cfg["max"]
        ws_dict = occupied[m_name]
        sorted_occupied = sorted(ws_dict.keys())

        global_bound: Set[int] = set()
        other_occupied: Set[int] = set()
        for other_m, other_cfg in configs.items():
            if other_m != m_name:
                global_bound.update(range(other_cfg["base"], other_cfg["max"] + 1))
                other_occupied.update(occupied.get(other_m, {}).keys())

        expected = _build_targets(len(sorted_occupied), base, max_ws, global_bound, other_occupied, max_pool_ws)
        if sorted_occupied == expected:
            continue

        active_ws = mon_info_map[m_name].get("activeWorkspace", {}).get("id", base)
        new_active_ws = active_ws
        if sorted_occupied:
            if active_ws in sorted_occupied:
                new_active_ws = expected[sorted_occupied.index(active_ws)]
            elif active_ws > max(sorted_occupied):
                new_active_ws = _build_targets(len(sorted_occupied) + 1, base, max_ws, global_bound, other_occupied, max_pool_ws)[-1]
            elif active_ws < min(sorted_occupied):
                new_active_ws = expected[0]
            else:
                for idx, w in enumerate(sorted_occupied):
                    if w > active_ws:
                        new_active_ws = expected[idx]
                        break
        else:
            new_active_ws = base

        for old_ws, target_ws in zip(sorted_occupied, expected):
            if old_ws == target_ws:
                continue
            for addr in ws_dict[old_ws]:
                all_dispatches.append(f"dispatch movetoworkspacesilent {target_ws},address:{addr}")

        if new_active_ws != active_ws:
            all_dispatches.append(f"dispatch focusmonitor {m_name}")
            all_dispatches.append(f"dispatch workspace {new_active_ws}")

    if all_dispatches:
        if focused_mon:
            all_dispatches.append(f"dispatch focusmonitor {focused_mon}")
        hypr_batch(all_dispatches)
        return True

    return False


def drain_socket(sock: socket.socket) -> None:
    """Draine les événements résiduels en attente sur socket2 pour briser l'écho."""
    while True:
        rlist, _, _ = select.select([sock], [], [], 0.0)
        if not rlist:
            break
        try:
            if not sock.recv(4096):
                break
        except (BlockingIOError, socket.error):
            break


def run_daemon():
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    compact_workspaces()
    debounce_delay = 0.08
    force_rescan = False

    while running:
        _, event_sock_path = get_hypr_sockets(force_rescan=force_rescan)
        if not event_sock_path or not os.path.exists(event_sock_path):
            force_rescan = True
            time.sleep(1.0)
            continue

        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(event_sock_path)
            s.setblocking(False)
            force_rescan = False
        except (socket.error, OSError, TimeoutError):
            force_rescan = True
            time.sleep(1.0)
            continue

        buffer = ""
        pending_compact_time = None
        is_compacting = False

        try:
            while running:
                now = time.time()
                timeout = max(0.0, pending_compact_time - now) if pending_compact_time is not None else None
                rlist, _, _ = select.select([s], [], [], timeout)

                if s in rlist:
                    data = s.recv(4096)
                    if not data:
                        force_rescan = True
                        break
                    buffer += data.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        event_name = line.split(">>")[0]
                        if event_name == "configreloaded" or event_name.startswith(("monitoradded", "monitorremoved")):
                            get_monitor_configs(force_refresh=True)
                        if not is_compacting and event_name in ("closewindow", "destroyworkspace", "movewindow"):
                            pending_compact_time = time.time() + debounce_delay

                if pending_compact_time is not None and time.time() >= pending_compact_time:
                    pending_compact_time = None
                    is_compacting = True
                    try:
                        if compact_workspaces():
                            time.sleep(0.01)
                            drain_socket(s)
                            buffer = ""
                    finally:
                        is_compacting = False
        except (socket.error, OSError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
            force_rescan = True
        finally:
            try:
                s.close()
            except OSError:
                pass

        if running:
            time.sleep(1.0)


def main():
    if "--once" in sys.argv:
        changed = compact_workspaces()
        print(f"Compacted: {changed}")
        return

    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    lock_file = os.fdopen(fd, "r+", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, BlockingIOError):
        lock_file.close()
        print("Workspace auto-compactor is already running.", file=sys.stderr)
        sys.exit(0)

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()

    run_daemon()


if __name__ == "__main__":
    main()
