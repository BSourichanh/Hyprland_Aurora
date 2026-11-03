#!/usr/bin/env python3
"""
Hyprland IPC & UNIX Domain Command Socket Handler for Spotify Card.
Manages compositor IPC queries, window positioning, and socket commands.

Design Patterns:
- Service Pattern: HyprlandIPCService for compositor interaction via UNIX socket.
- Command Pattern: IPCCommandHandler dispatches named commands to window callbacks.
"""

import fcntl
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from typing import Callable, Dict, Optional, Tuple

# Ensure module directory is on sys.path for direct CLI execution
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

COMMAND_SOCK = "/tmp/spotify_card.sock"
LOCK_FILE = "/tmp/spotify_card.lock"
_lock_fd = None


class HyprlandIPCService:
    """Service handling Hyprland UNIX socket IPC queries and dispatches."""

    def __init__(self):
        self._cached_sock: Optional[str] = None

    def get_socket_path(self) -> Optional[str]:
        if self._cached_sock and os.path.exists(self._cached_sock):
            return self._cached_sock
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        if sig:
            sock = f"{xdg}/hypr/{sig}/.socket.sock"
            if os.path.exists(sock):
                self._cached_sock = sock
                return sock
        return None

    def get_cursor_position(self) -> Tuple[Optional[int], Optional[int]]:
        sock_path = self.get_socket_path()
        if not sock_path:
            return None, None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.04)
                s.connect(sock_path)
                s.sendall(b"cursorpos")
                res = s.recv(1024).decode().strip()
                parts = res.split(",")
                return int(parts[0].strip()), int(parts[1].strip())
        except (socket.error, OSError, TimeoutError, ValueError, IndexError):
            return None, None

    def move_window_pixel(self, x: int, y: int, window_class: str = "spotify-card"):
        sock_path = self.get_socket_path()
        if not sock_path:
            return
        cmd = f"dispatch movewindowpixel exact {x} {y},class:{window_class}"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.05)
                s.connect(sock_path)
                s.sendall(cmd.encode())
                s.recv(1024)
        except (socket.error, OSError, TimeoutError):
            pass


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
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.sock_path)
        server.listen(5)
        while True:
            try:
                conn, _ = server.accept()
                data = conn.recv(1024).decode().strip()
                conn.sendall(b"OK\n")
                conn.close()
                self.handler.handle(data)
            except (socket.error, OSError, TimeoutError, UnicodeDecodeError):
                pass


def acquire_singleton_lock(lock_path: str = LOCK_FILE) -> bool:
    """Acquires a non-blocking flock to guarantee a singleton daemon instance."""
    global _lock_fd
    try:
        _lock_fd = open(lock_path, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, BlockingIOError):
        return False


def send_client_cmd(cmd: str, sock_path: str = COMMAND_SOCK) -> bool:
    """Sends a one-off command string to the running daemon via UNIX domain socket."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(sock_path)
            s.sendall(cmd.encode())
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
        # Client commands to running daemon (toggle, show, hide, like, masquer)
        send_client_cmd(cmd)


if __name__ == "__main__":
    main()
