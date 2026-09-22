#!/usr/bin/env python3
"""
Hyprland Dynamic Workspace Auto-Compactor
Compacts workspace numbering dynamically per monitor to eliminate gaps.
- DP-2 (left monitor): Base workspace 1 (1, 2, 3...)
- DP-1 (right monitor): Base workspace 6 (6, 7, 8...)
"""

import os
import sys
import json
import time
import socket
import select
import signal
import fcntl

LOCK_FILE = "/tmp/hypr_workspace_autocompact.lock"


def get_hypr_socket_paths():
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not runtime_dir or not his:
        return None, None
    base_dir = os.path.join(runtime_dir, "hypr", his)
    cmd_sock = os.path.join(base_dir, ".socket.sock")
    event_sock = os.path.join(base_dir, ".socket2.sock")
    return cmd_sock, event_sock


def hypr_cmd(command: str) -> str:
    cmd_sock_path, _ = get_hypr_socket_paths()
    if not cmd_sock_path or not os.path.exists(cmd_sock_path):
        return ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(cmd_sock_path)
            s.sendall(command.encode("utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception:
        return ""


def hypr_batch(dispatches: list) -> str:
    if not dispatches:
        return ""
    batch_str = "[[BATCH]]" + ";".join(dispatches)
    return hypr_cmd(batch_str)


def hypr_json(query: str):
    raw = hypr_cmd(query)
    try:
        return json.loads(raw)
    except Exception:
        return []


def get_monitor_configs():
    rules = hypr_json("j/workspacerules")
    mon_workspaces = {}
    for r in rules:
        ws_str = r.get("workspaceString", "")
        mon = r.get("monitor", "")
        if ws_str.isdigit() and mon:
            ws_id = int(ws_str)
            mon_workspaces.setdefault(mon, []).append(ws_id)

    configs = {
        "DP-2": {"base": 1, "max": 5},
        "DP-1": {"base": 6, "max": 10},
    }
    for mon, ids in mon_workspaces.items():
        if ids:
            configs[mon] = {"base": min(ids), "max": max(ids)}
    return configs


def compact_workspaces():
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
        mon_info_map[mon_name] = m
        if m.get("focused"):
            focused_mon = mon_name

    ws_mon_map = {}
    for ws in workspaces:
        ws_id = ws.get("id")
        ws_mon = ws.get("monitor")
        if ws_id is not None and ws_mon:
            ws_mon_map[ws_id] = ws_mon

    def get_ws_monitor(ws_id: int) -> str:
        if ws_id in ws_mon_map:
            return ws_mon_map[ws_id]
        for m_name, cfg in configs.items():
            if cfg["base"] <= ws_id <= cfg["max"]:
                return m_name
        return "DP-1" if ws_id >= 6 else "DP-2"

    occupied = {}
    for m_name in configs.keys():
        occupied[m_name] = {}

    for c in clients:
        if not c.get("mapped") or c.get("pinned"):
            continue
        ws_info = c.get("workspace", {})
        ws_id = ws_info.get("id")
        if ws_id is None or ws_id < 1:
            continue
        addr = c.get("address")
        if not addr:
            continue
        m_name = get_ws_monitor(ws_id)
        if m_name in occupied:
            occupied[m_name].setdefault(ws_id, []).append(addr)

    all_dispatches = []

    for m_name, cfg in configs.items():
        if m_name not in mon_info_map:
            continue
        base = cfg["base"]
        ws_dict = occupied[m_name]
        sorted_occupied = sorted(ws_dict.keys())

        expected = [base + i for i in range(len(sorted_occupied))]
        if sorted_occupied == expected:
            continue

        active_ws = mon_info_map[m_name].get("activeWorkspace", {}).get("id", base)

        # Calculate new active workspace
        new_active_ws = active_ws
        if sorted_occupied:
            if active_ws in sorted_occupied:
                idx = sorted_occupied.index(active_ws)
                new_active_ws = base + idx
            elif active_ws > max(sorted_occupied):
                new_active_ws = base + len(sorted_occupied)
            elif active_ws < min(sorted_occupied):
                new_active_ws = base
            else:
                for idx, w in enumerate(sorted_occupied):
                    if w > active_ws:
                        new_active_ws = base + idx
                        break
        else:
            new_active_ws = base

        # Move windows in ascending order so targets are always free
        for i, old_ws in enumerate(sorted_occupied):
            target_ws = base + i
            if old_ws == target_ws:
                continue
            for addr in ws_dict[old_ws]:
                all_dispatches.append(f"dispatch movetoworkspacesilent {target_ws},address:{addr}")

        if new_active_ws != active_ws:
            all_dispatches.append(f"dispatch workspace {new_active_ws}")

    if all_dispatches:
        if focused_mon:
            all_dispatches.append(f"dispatch focusmonitor {focused_mon}")
        hypr_batch(all_dispatches)
        return True

    return False


def run_daemon():
    _, event_sock_path = get_hypr_socket_paths()
    if not event_sock_path or not os.path.exists(event_sock_path):
        print("Hyprland event socket not found.", file=sys.stderr)
        sys.exit(1)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(event_sock_path)
    s.setblocking(False)

    buffer = ""
    debounce_delay = 0.08
    pending_compact_time = None
    is_compacting = False

    def handle_signal(sig, frame):
        s.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Initial compaction check at startup
    compact_workspaces()

    while True:
        now = time.time()
        timeout = None
        if pending_compact_time is not None:
            timeout = max(0.0, pending_compact_time - now)

        rlist, _, _ = select.select([s], [], [], timeout)

        if s in rlist:
            try:
                data = s.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    event_name = line.split(">>")[0]
                    if not is_compacting and event_name in (
                        "closewindow",
                        "destroyworkspace",
                        "movewindow",
                    ):
                        pending_compact_time = time.time() + debounce_delay
            except Exception:
                pass

        if pending_compact_time is not None and time.time() >= pending_compact_time:
            pending_compact_time = None
            is_compacting = True
            try:
                compact_workspaces()
            finally:
                is_compacting = False


def main():
    if "--once" in sys.argv:
        changed = compact_workspaces()
        print(f"Compacted: {changed}")
        return

    # Daemon mode: acquire singleton lock
    lock_file = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Workspace auto-compactor is already running.", file=sys.stderr)
        sys.exit(0)

    lock_file.write(str(os.getpid()))
    lock_file.flush()

    run_daemon()


if __name__ == "__main__":
    main()
