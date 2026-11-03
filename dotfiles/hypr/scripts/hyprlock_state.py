#!/usr/bin/env python3
"""
Hyprlock State & Multi-Monitor Workspace Isolation Manager
Handles atomic state capture, reserved workspace redirection (97/98/99),
client expulsion, hotplug watcher, and deterministic workspace restoration.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time

STATE_FILE = "/tmp/hypr_lock_orig_workspaces.json"
LOCK_FILE = "/tmp/hypr_locked"


def get_hypr_sockets():
    """Resolves Hyprland command and event sockets."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if runtime_dir and his:
        base_dir = os.path.join(runtime_dir, "hypr", his)
        cmd_sock = os.path.join(base_dir, ".socket.sock")
        event_sock = os.path.join(base_dir, ".socket2.sock")
        if os.path.exists(cmd_sock) and os.path.exists(event_sock):
            return cmd_sock, event_sock
    if runtime_dir:
        hypr_dir = os.path.join(runtime_dir, "hypr")
        if os.path.exists(hypr_dir):
            try:
                candidates = sorted(
                    [os.path.join(hypr_dir, d) for d in os.listdir(hypr_dir)],
                    key=lambda p: os.path.getmtime(p) if os.path.isdir(p) else 0,
                    reverse=True,
                )
                for cdir in candidates:
                    cmd_sock = os.path.join(cdir, ".socket.sock")
                    event_sock = os.path.join(cdir, ".socket2.sock")
                    if os.path.exists(cmd_sock) and os.path.exists(event_sock):
                        return cmd_sock, event_sock
            except (OSError, ValueError):
                pass
    return None, None


def hypr_cmd(cmd: str) -> str:
    """Sends a raw command or query to Hyprland's primary socket."""
    cmd_sock, _ = get_hypr_sockets()
    if not cmd_sock or not os.path.exists(cmd_sock):
        return ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(cmd_sock)
            s.sendall(cmd.encode("utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks).decode("utf-8", errors="replace")
    except (socket.error, OSError, TimeoutError):
        return ""


def save_state():
    """Saves original active workspaces per monitor before locking."""
    prev_state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                prev_state = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    raw = hypr_cmd("j/monitors")
    if not raw:
        return
    try:
        monitors = json.loads(raw)
        state = {}
        for m in monitors:
            name = m.get("name")
            ws_id = m.get("activeWorkspace", {}).get("id")
            if ws_id in (97, 98, 99):
                prev_ws = prev_state.get(name)
                ws_id = (
                    prev_ws
                    if (prev_ws and prev_ws not in (97, 98, 99))
                    else (1 if name == "DP-2" else (6 if name == "DP-1" else 1))
                )
            state[name] = ws_id
            if m.get("focused"):
                state["__focused__"] = name
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        pass


def switch_reserved():
    """Redirects monitors to empty lock workspaces (98 on DP-2, 99 on DP-1, 97 others)."""
    raw = hypr_cmd("j/monitors")
    if not raw:
        return
    try:
        monitors = json.loads(raw)
        cmds = []
        for m in monitors:
            name = m.get("name")
            if name == "DP-2":
                cmds.append("dispatch focusmonitor DP-2;dispatch workspace 98")
            elif name == "DP-1":
                cmds.append("dispatch focusmonitor DP-1;dispatch workspace 99")
            else:
                cmds.append(f"dispatch focusmonitor {name};dispatch workspace 97")
        if cmds:
            hypr_cmd("[[BATCH]]" + ";".join(cmds))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass


def expel_clients():
    """Expels any window that inadvertently spawned on reserved lock workspaces."""
    raw_m = hypr_cmd("j/monitors")
    connected_names = set()
    if raw_m:
        try:
            connected_names = {m.get("name") for m in json.loads(raw_m) if m.get("name")}
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    raw_c = hypr_cmd("j/clients")
    if not raw_c:
        return
    try:
        clients = json.loads(raw_c)
        cmds = []
        for c in clients:
            if c.get("class") == "Paros":
                continue
            ws_id = c.get("workspace", {}).get("id")
            addr = c.get("address")
            if ws_id in (97, 98, 99) and addr:
                target_ws = (
                    2
                    if (ws_id == 98 and "DP-2" in connected_names)
                    else (6 if (ws_id == 99 and "DP-1" in connected_names) else 1)
                )
                cmds.append(f"dispatch movetoworkspacesilent {target_ws},address:{addr}")
        if cmds:
            hypr_cmd("[[BATCH]]" + ";".join(cmds))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass


def restore_state():
    """Restores saved original workspaces to connected monitors upon unlocking."""
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, "r") as f:
            orig = json.load(f)
        raw_m = hypr_cmd("j/monitors")
        monitors = json.loads(raw_m) if raw_m else []
        cmds = []
        focused_mon = orig.get("__focused__")
        for m in monitors:
            name = m.get("name")
            if name in orig:
                orig_ws = orig[name]
                if orig_ws in (97, 98, 99):
                    orig_ws = 1 if name == "DP-2" else (6 if name == "DP-1" else 1)
                cmds.append(f"dispatch focusmonitor {name};dispatch workspace {orig_ws}")
        if focused_mon and any(m.get("name") == focused_mon for m in monitors):
            cmds.append(f"dispatch focusmonitor {focused_mon}")
        if cmds:
            hypr_cmd("[[BATCH]]" + ";".join(cmds))
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        pass


def enforce_lock():
    """Forces all monitors back onto reserved workspaces and purges rogue clients."""
    if not os.path.exists(LOCK_FILE):
        return
    try:
        raw = hypr_cmd("j/monitors")
        if not raw:
            return
        monitors = json.loads(raw)
        connected_names = {m.get("name") for m in monitors if m.get("name")}
        cmds = []
        for m in monitors:
            name = m.get("name")
            if not name or not m.get("activeWorkspace"):
                continue
            act = m.get("activeWorkspace", {}).get("id")
            if name == "DP-2" and act != 98:
                cmds.append("dispatch focusmonitor DP-2;dispatch workspace 98")
            elif name == "DP-1" and act != 99:
                cmds.append("dispatch focusmonitor DP-1;dispatch workspace 99")
            elif name not in ("DP-1", "DP-2") and act != 97:
                cmds.append(f"dispatch focusmonitor {name};dispatch workspace 97")

        raw_c = hypr_cmd("j/clients")
        if raw_c:
            clients = json.loads(raw_c)
            for c in clients:
                if c.get("class") == "Paros":
                    continue
                ws_id = c.get("workspace", {}).get("id")
                addr = c.get("address")
                if ws_id in (97, 98, 99) and addr:
                    target_ws = (
                        2
                        if (ws_id == 98 and "DP-2" in connected_names)
                        else (6 if (ws_id == 99 and "DP-1" in connected_names) else 1)
                    )
                    cmds.append(f"dispatch movetoworkspacesilent {target_ws},address:{addr}")
        if cmds:
            hypr_cmd("[[BATCH]]" + ";".join(cmds))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass


def run_watcher():
    """Background daemon monitoring monitor hotplug and events during lock."""
    def handle_signal(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _, event_sock_path = get_hypr_sockets()
    if not event_sock_path or not os.path.exists(event_sock_path):
        sys.exit(1)

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(event_sock_path)
    except (socket.error, OSError, TimeoutError):
        sys.exit(1)

    buf = ""
    while os.path.exists(LOCK_FILE):
        try:
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
                    time.sleep(0.3)
                    enforce_lock()
                    subprocess.run(["killall", "waybar"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["pkill", "-f", "spotify.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["pkill", "-f", "gpu.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["pkill", "-f", "swaync-client -swb"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif ev == "configreloaded":
                    hypr_cmd("keyword misc:disable_autoreload true")
                    time.sleep(0.2)
                    enforce_lock()
                elif ev in ("workspace", "workspacev2", "focusedmon", "openwindow", "mapwindow"):
                    enforce_lock()
        except (socket.error, OSError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
            break
    s.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: hyprlock_state.py [save|switch-reserved|expel-clients|restore|watch|enforce]")
        sys.exit(1)

    action = sys.argv[1]
    if action == "save":
        save_state()
    elif action == "switch-reserved":
        switch_reserved()
    elif action == "expel-clients":
        expel_clients()
    elif action == "restore":
        restore_state()
    elif action == "watch":
        run_watcher()
    elif action == "enforce":
        enforce_lock()
    else:
        print(f"Action inconnue: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
