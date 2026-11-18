#!/usr/bin/env python3
"""
Hyprland IPC Event Daemon for Aurora Wallpaper Engine
Monitors Hyprland socket2 events (monitoradded, monitorremoved, configreloaded, dpms).
"""

import contextlib
import fcntl
import os
import select
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List

try:
    from aurora_runtime import get_lock_state, open_secure_lock
except ImportError:
    from scripts.aurora_runtime import get_lock_state, open_secure_lock


def get_event_socket_path() -> str:
    """Resolves Hyprland IPC event socket path (.socket2.sock)."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if runtime_dir and his:
        candidate = os.path.join(runtime_dir, "hypr", his, ".socket2.sock")
        if os.path.exists(candidate):
            return candidate
    if runtime_dir and os.path.exists(os.path.join(runtime_dir, "hypr")):
        for entry in os.listdir(os.path.join(runtime_dir, "hypr")):
            candidate = os.path.join(runtime_dir, "hypr", entry, ".socket2.sock")
            if os.path.exists(candidate):
                return candidate
    return ""


def _cleanup_lock(lock_f, lock_path: Path) -> None:
    """Releases flock, closes descriptor, and unlinks daemon lockfile."""
    with contextlib.suppress(Exception):
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    with contextlib.suppress(Exception):
        lock_f.close()
    if lock_path.exists() and not lock_path.is_symlink():
        with contextlib.suppress(OSError):
            lock_path.unlink()


def run_wallpaper_daemon(
    daemon_lock_path: Path,
    ensure_wallpapers: Callable[[], None],
    get_active_layers: Callable[[], Dict[str, int]],
    get_connected_screens: Callable[[], List[str]],
) -> None:
    """Continuous background daemon monitoring Hyprland monitor and DPMS events."""
    try:
        lock_f = open_secure_lock(daemon_lock_path)
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_f.seek(0)
        lock_f.write(str(os.getpid()))
        lock_f.truncate()
        lock_f.flush()
    except (BlockingIOError, IOError, OSError):
        print("Le démon Wallpaper Engine est déjà actif.", file=sys.stderr)
        sys.exit(0)

    event_sock_path = get_event_socket_path()
    if not event_sock_path or not os.path.exists(event_sock_path):
        print("Erreur: Socket événement Hyprland introuvable.", file=sys.stderr)
        _cleanup_lock(lock_f, daemon_lock_path)
        sys.exit(1)

    def handle_exit(sig, frame):
        _cleanup_lock(lock_f, daemon_lock_path)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    if not get_lock_state(clean_orphans=True)["locked"]:
        ensure_wallpapers()

    print(f"✓ Démon Wallpaper Engine démarré (PID {os.getpid()}), écoute sur {event_sock_path}...")
    sys.stdout.flush()

    debounce_delay = 0.4
    fallback_interval = 10.0
    last_watchdog_check = time.time()
    pending_ensure = 0.0
    monitor_events = ("monitoradded", "monitorremoved", "configreloaded", "dpms")

    while True:
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(event_sock_path)
            sock.setblocking(False)
            buf = ""
            while True:
                now = time.time()
                timeout = 2.0
                if pending_ensure > 0.0:
                    timeout = min(timeout, max(0.0, pending_ensure - now))

                rlist, _, _ = select.select([sock], [], [], timeout)
                if sock in rlist:
                    data = sock.recv(4096)
                    if not data:
                        break
                    buf += data.decode("utf-8", errors="replace")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        ev_type = line.split(">>")[0]
                        if any(ev_type.startswith(ev) for ev in monitor_events):
                            if not get_lock_state(clean_orphans=True)["locked"]:
                                pending_ensure = time.time() + debounce_delay

                now_check = time.time()
                if pending_ensure > 0.0:
                    if now_check >= pending_ensure:
                        pending_ensure = 0.0
                        if not get_lock_state(clean_orphans=True)["locked"]:
                            ensure_wallpapers()
                        last_watchdog_check = now_check
                elif now_check - last_watchdog_check >= fallback_interval:
                    last_watchdog_check = now_check
                    if not get_lock_state(clean_orphans=True)["locked"]:
                        active_layers = get_active_layers()
                        connected = get_connected_screens()
                        if any(scr not in active_layers for scr in connected):
                            ensure_wallpapers()
        except Exception:
            time.sleep(1.0)
            event_sock_path = get_event_socket_path()
            if not event_sock_path or not os.path.exists(event_sock_path):
                time.sleep(2.0)
        finally:
            if sock is not None:
                with contextlib.suppress(OSError):
                    sock.close()
