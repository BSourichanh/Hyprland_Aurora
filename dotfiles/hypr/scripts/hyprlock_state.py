#!/usr/bin/env python3
"""
Hyprlock State & Multi-Monitor Workspace Isolation Manager
Handles atomic state capture, disjoint reserved workspaces (90..99),
special workspace closure, pinned client hiding/unpinning (Paros/spotify-card),
hotplug watcher, and deterministic workspace restoration.
"""

import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time
from typing import Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hypr_ipc import (
    atomic_write_json,
    get_aurora_runtime_dir,
    get_hypr_sockets,
    hypr_batch,
    hypr_cmd,
    hypr_json,
)

RUNTIME_DIR = get_aurora_runtime_dir()
STATE_FILE = str(RUNTIME_DIR / "hypr_lock_orig_workspaces.json")
LOCK_FILE = str(RUNTIME_DIR / "hypr_locked")
RESERVED_WS_MIN = 90
RESERVED_WS_MAX = 99


def is_reserved_ws(ws_id) -> bool:
    return isinstance(ws_id, int) and RESERVED_WS_MIN <= ws_id <= RESERVED_WS_MAX


def set_disable_autoreload(enabled: bool = True) -> None:
    """Sets misc:disable_autoreload via 0.57.2 Lua eval with 0.56.2 keyword fallback."""
    flag = "true" if enabled else "false"
    resp = hypr_cmd(f"eval hl.config({{ misc = {{ disable_autoreload = {flag} }} }})")
    resp_lower = (resp or "").lower()
    if "lua config manager" in resp_lower or "unknown request" in resp_lower:
        hypr_cmd(f"keyword misc:disable_autoreload {flag}")


def default_user_ws(mon_name: str) -> int:
    if mon_name == "DP-1":
        return 6
    return 1


def get_reserved_ws_map(monitors: List[dict]) -> Dict[str, int]:
    """Assigns strictly disjoint reserved workspaces (98/99/97/96/...) per monitor."""
    mapping: Dict[str, int] = {}
    for m in monitors:
        name = m.get("name")
        if name == "DP-2":
            mapping[name] = 98
        elif name == "DP-1":
            mapping[name] = 99
    next_ws = 97
    for m in sorted(monitors, key=lambda x: x.get("name") or ""):
        name = m.get("name")
        if not name or name in mapping:
            continue
        while next_ws in (98, 99) or next_ws in mapping.values():
            next_ws -= 1
        mapping[name] = max(RESERVED_WS_MIN, next_ws)
        next_ws -= 1
    return mapping


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return {}


def _record_unpinned_addrs(addrs: List[str]) -> None:
    if not addrs:
        return
    state = _load_state()
    existing = state.get("__unpinned__", [])
    if not isinstance(existing, list):
        existing = []
    for addr in addrs:
        if addr not in existing:
            existing.append(addr)
    state["__unpinned__"] = existing
    try:
        atomic_write_json(STATE_FILE, state)
    except OSError:
        pass


def save_state():
    """Saves original active workspaces per monitor before locking."""
    prev_state = _load_state()
    monitors = hypr_json("j/monitors")
    if not isinstance(monitors, list) or not monitors:
        return
    state: dict = {}
    if isinstance(prev_state.get("__unpinned__"), list):
        state["__unpinned__"] = prev_state["__unpinned__"]
    for m in monitors:
        name = m.get("name")
        if not name:
            continue
        ws_id = m.get("activeWorkspace", {}).get("id")
        if is_reserved_ws(ws_id):
            prev_ws = prev_state.get(name)
            ws_id = prev_ws if (isinstance(prev_ws, int) and not is_reserved_ws(prev_ws)) else default_user_ws(name)
        state[name] = ws_id
        if m.get("focused"):
            state["__focused__"] = name
    try:
        atomic_write_json(STATE_FILE, state)
    except OSError:
        pass


def _dsp_focus_mon(name: str) -> str:
    return f'dispatch hl.dsp.focus({{ monitor = "{name}" }})'


def _dsp_focus_ws(ws: int) -> str:
    return f'dispatch hl.dsp.focus({{ workspace = {ws} }})'


def _special_ws_close_cmds(monitors: List[dict]) -> List[str]:
    cmds = []
    for m in monitors:
        name = m.get("name")
        sp = m.get("specialWorkspace", {})
        if not name or not isinstance(sp, dict):
            continue
        if sp.get("id", 0) != 0 or sp.get("name"):
            sp_name = str(sp.get("name", ""))
            if sp_name.startswith("special:"):
                sp_name = sp_name[len("special:"):]
            cmds.append(_dsp_focus_mon(name))
            arg = f'"{sp_name}"' if sp_name else ""
            cmds.append(f"dispatch hl.dsp.workspace.toggle_special({arg})")
    return cmds


def switch_reserved():
    """Redirects monitors to disjoint reserved lock workspaces and closes special workspaces."""
    monitors = hypr_json("j/monitors")
    if not isinstance(monitors, list) or not monitors:
        return
    reserved_map = get_reserved_ws_map(monitors)
    cmds = _special_ws_close_cmds(monitors)
    for m in monitors:
        name = m.get("name")
        if name in reserved_map:
            cmds.extend([_dsp_focus_mon(name), _dsp_focus_ws(reserved_map[name])])
    if cmds:
        hypr_batch(cmds)


def _target_ws_for_expel(ws_id, connected_names: set) -> int:
    if ws_id == 98 and "DP-2" in connected_names:
        return 2
    if ws_id == 99 and "DP-1" in connected_names:
        return 6
    if "DP-2" in connected_names:
        return 1
    if "DP-1" in connected_names:
        return 6
    return 1


def _build_client_expel_cmds(clients: list, connected_names: set) -> tuple:
    cmds = []
    newly_unpinned = []
    for c in clients:
        addr = c.get("address")
        if not addr:
            continue
        cls = c.get("class", "")
        ws_id = c.get("workspace", {}).get("id")
        is_pinned = bool(c.get("pinned"))
        is_sensitive = cls in ("Paros", "spotify-card")
        if not is_pinned and not is_reserved_ws(ws_id) and not (is_sensitive and c.get("mapped")):
            continue
        if is_pinned:
            cmds.append(f'dispatch hl.dsp.window.pin({{ window = "address:{addr}" }})')
            newly_unpinned.append(addr)
        if is_reserved_ws(ws_id) or is_pinned or (is_sensitive and c.get("mapped")):
            target_ws = _target_ws_for_expel(ws_id, connected_names)
            cmds.append(f'dispatch hl.dsp.window.move({{ workspace = {target_ws}, window = "address:{addr}", silent = true }})')
    return cmds, newly_unpinned


def expel_clients():
    """Expels and unpins windows (including Paros/spotify-card) from reserved lock workspaces."""
    monitors = hypr_json("j/monitors")
    connected_names = {m.get("name") for m in monitors if isinstance(m, dict) and m.get("name")} if isinstance(monitors, list) else set()
    clients = hypr_json("j/clients")
    if not isinstance(clients, list):
        return
    cmds, newly_unpinned = _build_client_expel_cmds(clients, connected_names)
    if newly_unpinned:
        _record_unpinned_addrs(newly_unpinned)
    if cmds:
        hypr_batch(cmds)


def restore_state():
    """Restores saved original workspaces and re-pins temporarily unpinned clients."""
    orig = _load_state()
    if not orig:
        return
    monitors = hypr_json("j/monitors")
    if not isinstance(monitors, list):
        monitors = []
    cmds = []
    focused_mon = orig.get("__focused__")
    for m in monitors:
        name = m.get("name")
        if not name:
            continue
        orig_ws = orig.get(name)
        if not isinstance(orig_ws, int) or is_reserved_ws(orig_ws):
            orig_ws = default_user_ws(name)
        cmds.extend([_dsp_focus_mon(name), _dsp_focus_ws(orig_ws)])

    unpinned_addrs = orig.get("__unpinned__", [])
    if isinstance(unpinned_addrs, list) and unpinned_addrs:
        clients = hypr_json("j/clients")
        if isinstance(clients, list):
            by_addr = {c.get("address"): c for c in clients if isinstance(c, dict)}
            for addr in unpinned_addrs:
                c = by_addr.get(addr)
                if c and not c.get("pinned"):
                    cmds.append(f'dispatch hl.dsp.window.pin({{ window = "address:{addr}" }})')

    if focused_mon and any(m.get("name") == focused_mon for m in monitors):
        cmds.append(_dsp_focus_mon(focused_mon))
    if cmds:
        hypr_batch(cmds)


def enforce_lock():
    """Forces all monitors onto disjoint reserved workspaces, closes special workspaces, expels rogue clients."""
    if not os.path.exists(LOCK_FILE):
        return
    monitors = hypr_json("j/monitors")
    if not isinstance(monitors, list) or not monitors:
        return
    reserved_map = get_reserved_ws_map(monitors)
    connected_names = set(reserved_map.keys())
    cmds = _special_ws_close_cmds(monitors)
    for m in monitors:
        name = m.get("name")
        if not name or not m.get("activeWorkspace"):
            continue
        act = m.get("activeWorkspace", {}).get("id")
        target_reserved = reserved_map.get(name)
        if target_reserved is not None and act != target_reserved:
            cmds.extend([_dsp_focus_mon(name), _dsp_focus_ws(target_reserved)])

    clients = hypr_json("j/clients")
    if isinstance(clients, list):
        c_cmds, newly_unpinned = _build_client_expel_cmds(clients, connected_names)
        if newly_unpinned:
            _record_unpinned_addrs(newly_unpinned)
        cmds.extend(c_cmds)
    if cmds:
        hypr_batch(cmds)


def run_watcher():
    """Background daemon monitoring monitor hotplug and events during lock."""
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _, event_sock_path = get_hypr_sockets()
    if not event_sock_path or not os.path.exists(event_sock_path):
        sys.exit(1)

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(event_sock_path)
        s.setblocking(False)
    except (socket.error, OSError, TimeoutError):
        sys.exit(1)

    buf = ""
    pending_enforce_time = None
    debounce_sec = 0.05

    while running and os.path.exists(LOCK_FILE):
        try:
            now = time.time()
            timeout = max(0.0, pending_enforce_time - now) if pending_enforce_time is not None else 0.5
            rlist, _, _ = select.select([s], [], [], timeout)

            if pending_enforce_time is not None and time.time() >= pending_enforce_time:
                pending_enforce_time = None
                enforce_lock()

            if s in rlist:
                data = s.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    ev = line.split(">>")[0]
                    if ev.startswith("monitoradded"):
                        parts = line.split(">>")
                        new_mon = parts[1].strip() if len(parts) > 1 else ""
                        if new_mon:
                            cur_state = _load_state()
                            if new_mon not in cur_state:
                                cur_state[new_mon] = default_user_ws(new_mon)
                                try:
                                    atomic_write_json(STATE_FILE, cur_state)
                                except OSError:
                                    pass
                        time.sleep(0.3)
                        enforce_lock()
                        for proc_args in (
                            ["pkill", "-TERM", "-x", "waybar"],
                            ["pkill", "-TERM", "-f", "waybar/scripts/spotify.py"],
                            ["pkill", "-TERM", "-f", "waybar/scripts/gpu.py"],
                            ["pkill", "-TERM", "-f", "swaync-client -swb"],
                        ):
                            subprocess.run(proc_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif ev == "configreloaded":
                        set_disable_autoreload(True)
                        time.sleep(0.2)
                        enforce_lock()
                    elif ev in ("workspace", "workspacev2", "focusedmon", "openwindow", "mapwindow", "activespecial"):
                        pending_enforce_time = time.time() + debounce_sec
        except (socket.error, OSError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
            break
    try:
        s.close()
    except OSError:
        pass


def main():
    if len(sys.argv) < 2:
        print("Usage: hyprlock_state.py [save|switch-reserved|expel-clients|restore|watch|enforce]")
        sys.exit(1)

    actions = {
        "save": save_state,
        "switch-reserved": switch_reserved,
        "expel-clients": expel_clients,
        "restore": restore_state,
        "watch": run_watcher,
        "enforce": enforce_lock,
    }
    fn = actions.get(sys.argv[1])
    if not fn:
        print(f"Action inconnue: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
    fn()


if __name__ == "__main__":
    main()