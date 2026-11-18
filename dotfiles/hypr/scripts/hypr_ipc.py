#!/usr/bin/env python3
"""Shared Hyprland UNIX socket IPC and secure Aurora runtime helpers."""

import fcntl
import json
import os
import socket
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_connect_failures = 0
_RUNTIME_DIR_CACHE: Dict[Tuple[int, str], Path] = {}
_SOCKETS_CACHE: Dict[Tuple[str, str], Tuple[str, str]] = {}


def get_aurora_runtime_dir() -> Path:
    """Returns $AURORA_RUNTIME_DIR with 0700 permissions."""
    uid = os.getuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR") or ""
    cache_key = (uid, xdg)
    cached = _RUNTIME_DIR_CACHE.get(cache_key)
    if cached is not None:
        return cached
    base = xdg or f"/run/user/{uid}"
    runtime_dir = Path(base) / "aurora"
    os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
    try:
        os.chmod(runtime_dir, 0o700)
    except OSError:
        pass
    _RUNTIME_DIR_CACHE[cache_key] = runtime_dir
    return runtime_dir


def atomic_write_json(path: str, data: Any) -> None:
    """Writes JSON atomically with 0600 permissions inside target directory."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp_", dir=str(target.parent))
    try:
        os.chmod(tmp_name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_name, str(target))
    except Exception:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def _check_flock_pair(flag_path: str, inst_lock_path: str, clean_orphan: bool) -> Optional[bool]:
    if not os.path.exists(flag_path):
        return None
    try:
        fd = os.open(inst_lock_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError as exc:
        if clean_orphan and isinstance(exc, FileNotFoundError):
            try:
                os.remove(flag_path)
            except OSError:
                pass
        return False
    try:
        with os.fdopen(fd, "r") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        if clean_orphan:
            try:
                os.remove(flag_path)
            except OSError:
                pass
        return False
    except (BlockingIOError, OSError):
        return True


def is_session_locked() -> bool:
    """Checks active lock via $AURORA_RUNTIME_DIR flag + flock (with /tmp fallback)."""
    runtime_dir = get_aurora_runtime_dir()
    res = _check_flock_pair(str(runtime_dir / "hypr_locked"), str(runtime_dir / "hypr_lock_instance.lock"), True)
    if res is not None:
        return res
    return bool(_check_flock_pair("/tmp/hypr_locked", "/tmp/hypr_lock_instance.lock", False))


def get_hypr_sockets(force_rescan: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """Resolves Hyprland command (.socket.sock) and event (.socket2.sock) paths."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""
    cache_key = (his, runtime_dir)

    if force_rescan or _connect_failures >= 3:
        _SOCKETS_CACHE.pop(cache_key, None)
        his_active = ""
    else:
        cached = _SOCKETS_CACHE.get(cache_key)
        if cached is not None:
            if os.path.exists(cached[0]) and os.path.exists(cached[1]):
                return cached
            _SOCKETS_CACHE.pop(cache_key, None)
        his_active = his

    if his_active:
        cdir = os.path.join(runtime_dir, "hypr", his_active)
        cmd_sock, event_sock = os.path.join(cdir, ".socket.sock"), os.path.join(cdir, ".socket2.sock")
        if os.path.exists(cmd_sock) and os.path.exists(event_sock):
            _SOCKETS_CACHE[cache_key] = (cmd_sock, event_sock)
            return cmd_sock, event_sock

    hypr_dir = os.path.join(runtime_dir, "hypr")
    candidates: List[str] = []
    if os.path.isdir(hypr_dir):
        try:
            candidates = sorted(
                (os.path.join(hypr_dir, d) for d in os.listdir(hypr_dir)),
                key=lambda p: os.path.getmtime(p) if os.path.isdir(p) else 0,
                reverse=True,
            )
        except OSError:
            pass
    for cdir in candidates:
        cmd_sock, event_sock = os.path.join(cdir, ".socket.sock"), os.path.join(cdir, ".socket2.sock")
        if os.path.exists(cmd_sock) and os.path.exists(event_sock):
            _SOCKETS_CACHE[cache_key] = (cmd_sock, event_sock)
            return cmd_sock, event_sock
    return None, None


def hypr_cmd(command: str, timeout: float = 1.0) -> str:
    """Sends a command or query to Hyprland's UNIX socket."""
    global _connect_failures
    cmd_sock, _ = get_hypr_sockets()
    if not cmd_sock:
        _connect_failures += 1
        if _connect_failures >= 3:
            get_hypr_sockets(force_rescan=True)
        return ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(cmd_sock)
            s.sendall(command.encode("utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data:
                    break
                chunks.append(data)
            _connect_failures = 0
            return b"".join(chunks).decode("utf-8", errors="replace")
    except (socket.error, OSError, TimeoutError):
        _connect_failures += 1
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
        his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""
        _SOCKETS_CACHE.pop((his, runtime_dir), None)
        if _connect_failures >= 3:
            get_hypr_sockets(force_rescan=True)
        return ""

def hypr_batch(dispatches: List[str], timeout: float = 1.0) -> str:
    """Executes multiple Hyprland dispatches in a single atomic batch."""
    return hypr_cmd("[[BATCH]]" + ";".join(dispatches), timeout=timeout) if dispatches else ""

def hypr_json(query: str, timeout: float = 1.0) -> Any:
    """Executes a Hyprland j/... query and parses JSON safely."""
    try:
        return json.loads(hypr_cmd(query, timeout=timeout))
    except (json.JSONDecodeError, ValueError, TypeError):
        return []

def get_cursor_position(timeout: float = 0.04) -> Tuple[Optional[int], Optional[int]]:
    """Queries current cursor coordinates via Hyprland socket."""
    res = hypr_cmd("cursorpos", timeout=timeout).strip()
    if "," not in res:
        return None, None
    try:
        x_s, y_s = res.split(",", 1)
        return int(x_s.strip()), int(y_s.strip())
    except (ValueError, IndexError):
        return None, None

def move_window_pixel(x: int, y: int, window_class: str = "spotify-card", timeout: float = 0.05) -> None:
    """Moves a floating window to exact pixel coordinates via Hyprland 0.57.2 Lua dispatcher."""
    hypr_cmd(f'dispatch hl.dsp.window.move({{ x = {int(x)}, y = {int(y)}, window = "class:{window_class}" }})', timeout=timeout)
