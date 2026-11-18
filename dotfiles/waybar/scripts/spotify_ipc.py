#!/usr/bin/env python3
"""
Hyprland IPC & UNIX Domain Command Socket Handler for Spotify Card.
Manages compositor IPC queries, dynamic monitor bounds, window positioning, and socket commands.
"""

import fcntl
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
HYPR_SCRIPTS_DIR = SCRIPT_DIR.parent.parent / "hypr" / "scripts"
for p in (SCRIPT_DIR, HYPR_SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from hypr_ipc import (
    get_aurora_runtime_dir,
    get_cursor_position as ipc_get_cursor_position,
    get_hypr_sockets,
    hypr_json,
    move_window_pixel as ipc_move_window_pixel,
)

RUNTIME_DIR = get_aurora_runtime_dir()
COMMAND_SOCK = str(RUNTIME_DIR / "spotify_card.sock")
LOCK_FILE = str(RUNTIME_DIR / "spotify_card.lock")
_lock_fd = None


class HyprlandIPCService:
    """Service handling Hyprland UNIX socket IPC queries and dynamic monitor geometry."""

    def __init__(self):
        self._monitors_cache: List[Tuple[int, int, int, int]] = []
        self._monitors_cache_ts = 0.0

    def get_socket_path(self) -> Optional[str]:
        cmd_sock, _ = get_hypr_sockets()
        return cmd_sock

    def get_cursor_position(self) -> Tuple[Optional[int], Optional[int]]:
        return ipc_get_cursor_position(timeout=0.04)

    def move_window_pixel(self, x: int, y: int, window_class: str = "spotify-card"):
        ipc_move_window_pixel(x, y, window_class=window_class, timeout=0.05)

    def get_monitor_rects(self, max_age: float = 2.0) -> List[Tuple[int, int, int, int]]:
        """Returns logical (x, y, width, height) rects for active monitors via hyprctl/socket."""
        now = time.monotonic()
        if self._monitors_cache and (now - self._monitors_cache_ts) <= max_age:
            return self._monitors_cache

        raw = hypr_json("j/monitors", timeout=0.2)
        rects: List[Tuple[int, int, int, int]] = []
        if isinstance(raw, list):
            for m in raw:
                if not isinstance(m, dict) or m.get("disabled"):
                    continue
                mx = int(m.get("x", 0))
                my = int(m.get("y", 0))
                scale = float(m.get("scale", 1.0) or 1.0)
                w = int(m.get("width", 1920))
                h = int(m.get("height", 1080))
                if int(m.get("transform", 0)) % 2 == 1:
                    w, h = h, w
                lw = max(1, int(w / scale))
                lh = max(1, int(h / scale))
                rects.append((mx, my, lw, lh))
        if rects:
            self._monitors_cache = rects
            self._monitors_cache_ts = now
        return self._monitors_cache or [(0, 0, 1920, 1080)]

    def get_monitor_rect_at(self, x: Optional[int], y: Optional[int]) -> Tuple[int, int, int, int]:
        """Finds the monitor rect containing (x, y), defaulting to the first monitor."""
        rects = self.get_monitor_rects()
        if x is not None and y is not None:
            for mx, my, mw, mh in rects:
                if mx <= x < mx + mw and my <= y < my + mh:
                    return mx, my, mw, mh
        return rects[0]

    def get_card_origin_for_cursor(self) -> Tuple[int, int]:
        """Computes dynamic Spotify card anchor (x, y) on the monitor under the cursor."""
        cx, cy = self.get_cursor_position()
        mx, my, mw, _ = self.get_monitor_rect_at(cx, cy)
        card_w = 465
        target_x = mx + max(10, min(mw - card_w - 10, int(round(mw * 0.3125))))
        return target_x, my + 44


class IPCCommandHandler:
    """Dispatches incoming IPC socket commands to registered window callbacks."""

    def __init__(self, actions: Optional[Dict[str, Callable[[], None]]] = None):
        self._commands: Dict[str, Callable[[], None]] = actions or {}

    def register(self, cmd_name: str, action: Callable[[], None]):
        self._commands[cmd_name] = action

    def handle(self, cmd_name: str):
        action = self._commands.get(cmd_name)
        if action:
            action()


class CommandSocketThread(threading.Thread):
    """UNIX Domain Socket listener for desktop actions."""

    def __init__(self, handler: IPCCommandHandler, sock_path: str = COMMAND_SOCK):
        super().__init__(daemon=True)
        self.handler = handler
        self.sock_path = sock_path

    def run(self):
        Path(self.sock_path).parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.sock_path)
        try:
            os.chmod(self.sock_path, 0o600)
        except OSError:
            pass
        server.listen(5)
        while True:
            conn = None
            try:
                conn, _ = server.accept()
                conn.settimeout(1.0)
                data = conn.recv(1024).decode("utf-8", errors="replace").strip()
                conn.sendall(b"OK\n")
                conn.close()
                conn = None
                self.handler.handle(data)
            except (socket.error, OSError, TimeoutError, UnicodeDecodeError):
                if conn is not None:
                    try:
                        conn.close()
                    except OSError:
                        pass


def acquire_singleton_lock(lock_path: str = LOCK_FILE) -> bool:
    """Acquires a non-blocking flock with 0600 permissions inside $AURORA_RUNTIME_DIR."""
    global _lock_fd
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    fd_obj = None
    try:
        raw_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fd_obj = os.fdopen(raw_fd, "r+", encoding="utf-8")
        fcntl.flock(fd_obj, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd_obj.seek(0)
        fd_obj.truncate()
        fd_obj.write(str(os.getpid()))
        fd_obj.flush()
        _lock_fd = fd_obj
        return True
    except (IOError, BlockingIOError, OSError):
        if fd_obj is not None:
            try:
                fd_obj.close()
            except OSError:
                pass
        return False


def send_client_cmd(cmd: str, sock_path: str = COMMAND_SOCK) -> bool:
    """Sends a one-off command string to the running daemon via UNIX domain socket."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(sock_path)
            s.sendall(cmd.encode("utf-8"))
            s.recv(1024)
            return True
    except (socket.error, OSError, TimeoutError):
        return False


def notify_waybar_signal11():
    try:
        subprocess.run(["pkill", "-RTMIN+11", "waybar"], stderr=subprocess.DEVNULL)
    except (subprocess.SubprocessError, OSError):
        pass


def main():
    if len(sys.argv) < 2:
        return

    cmd = sys.argv[1].lower().strip("-")

    if cmd in ("play-pause", "play_pause", "playpause"):
        try:
            from spotify_mpris import MPRISPlayerFacade
            MPRISPlayerFacade().play_pause()
            notify_waybar_signal11()
        except (OSError, ValueError, AttributeError, RuntimeError):
            pass
    elif cmd in ("next",):
        try:
            from spotify_mpris import MPRISPlayerFacade
            MPRISPlayerFacade().next()
            notify_waybar_signal11()
        except (OSError, ValueError, AttributeError, RuntimeError):
            pass
    elif cmd in ("prev", "previous"):
        try:
            from spotify_mpris import MPRISPlayerFacade
            MPRISPlayerFacade().previous()
            notify_waybar_signal11()
        except (OSError, ValueError, AttributeError, RuntimeError):
            pass
    elif cmd in ("position", "seek"):
        if len(sys.argv) > 2:
            arg = sys.argv[2]
            try:
                import dbus
                from spotify_mpris import MPRISPlayerFacade
                raw = arg.replace("+", "").strip()
                offset = float(raw)
                if arg.strip().startswith("-"):
                    offset = -abs(offset)
                bus = MPRISPlayerFacade().get_bus()
                player = bus.get_object("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2", introspect=False)
                iface = dbus.Interface(player, "org.mpris.MediaPlayer2.Player")
                iface.Seek(dbus.Int64(int(offset * 1000000)), timeout=0.2)
            except (OSError, ValueError, TimeoutError, AttributeError):
                pass
    else:
        send_client_cmd(cmd)


if __name__ == "__main__":
    main()