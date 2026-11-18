#!/usr/bin/env python3
"""
Shared Runtime, Locking, Process & Hardlink Helpers — Aurora Ecosystem
Implements CONTRAT-RUNTIME.md ($AURORA_RUNTIME_DIR, safe locks, proc checks, canonical hardlink audit).
"""

import contextlib
import fcntl
import json
import os
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXCLUDED_DOTFILE_EXTS = (".bak", "-bak", ".pyc")
_RUNTIME_DIR_CACHE: Dict[Tuple[int, str], Path] = {}
_HYPR_CMD_SOCK_CACHE: Dict[Tuple[int, str, str], str] = {}


def get_aurora_runtime_dir() -> Path:
    """Returns canonical $AURORA_RUNTIME_DIR with 0700 permissions."""
    uid = os.getuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR") or ""
    cache_key = (uid, xdg)
    cached = _RUNTIME_DIR_CACHE.get(cache_key)
    if cached is not None and cached.is_dir():
        return cached
    base = xdg or f"/run/user/{uid}"
    runtime_dir = Path(base) / "aurora"
    os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(runtime_dir, 0o700)
    _RUNTIME_DIR_CACHE[cache_key] = runtime_dir
    return runtime_dir


def _resolve_hypr_cmd_socket(
    uid: int,
    xdg: str,
    his: str,
    force_refresh: bool = False,
    exclude_path: str = "",
) -> str:
    """Resolves Hyprland command socket (.socket.sock) with cache keyed by (uid, xdg, his)."""
    cache_key = (uid, xdg, his)
    if force_refresh:
        _HYPR_CMD_SOCK_CACHE.clear()
    else:
        cached = _HYPR_CMD_SOCK_CACHE.get(cache_key)
        if cached and cached != exclude_path and os.path.exists(cached):
            return cached
        if cached:
            _HYPR_CMD_SOCK_CACHE.pop(cache_key, None)

    runtime_base = xdg or f"/run/user/{uid}"
    if his and not force_refresh:
        candidate = os.path.join(runtime_base, "hypr", his, ".socket.sock")
        if candidate != exclude_path and os.path.exists(candidate):
            _HYPR_CMD_SOCK_CACHE[cache_key] = candidate
            return candidate

    hypr_dir = os.path.join(runtime_base, "hypr")
    if os.path.isdir(hypr_dir):
        candidates: List[Tuple[float, str]] = []
        with contextlib.suppress(OSError):
            with os.scandir(hypr_dir) as entries:
                for entry in entries:
                    if not entry.is_dir():
                        continue
                    sock_path = os.path.join(entry.path, ".socket.sock")
                    if sock_path != exclude_path and os.path.exists(sock_path):
                        mtime = 0.0
                        with contextlib.suppress(OSError):
                            mtime = entry.stat().st_mtime
                        candidates.append((mtime, sock_path))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            best = candidates[0][1]
            _HYPR_CMD_SOCK_CACHE[cache_key] = best
            return best
    return ""


def hypr_socket_cmd(command: str, timeout: float = 1.0) -> str:
    """Sends a command or query to Hyprland .socket.sock over AF_UNIX."""
    uid = os.getuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR") or ""
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""
    cache_key = (uid, xdg, his)
    failed_sock = ""

    for attempt in range(2):
        sock_path = _resolve_hypr_cmd_socket(
            uid,
            xdg,
            his,
            force_refresh=(attempt > 0),
            exclude_path=failed_sock if attempt > 0 else "",
        )
        if not sock_path:
            return ""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(sock_path)
                sock.sendall(command.encode("utf-8"))
                chunks: List[bytes] = []
                while True:
                    data = sock.recv(8192)
                    if not data:
                        break
                    chunks.append(data)
            return b"".join(chunks).decode("utf-8", errors="replace")
        except (OSError, TimeoutError, ValueError):
            failed_sock = sock_path
            _HYPR_CMD_SOCK_CACHE.pop(cache_key, None)
    return ""


def hypr_socket_json(query: str, timeout: float = 1.0) -> Any:
    """Queries Hyprland JSON IPC via .socket.sock with safe hyprctl -j fallback."""
    wire_query = query if query.startswith("j/") else f"j/{query}"
    raw = hypr_socket_cmd(wire_query, timeout=timeout)
    if raw:
        with contextlib.suppress(json.JSONDecodeError, ValueError, TypeError):
            return json.loads(raw)

    sub_args = wire_query[2:].split()
    if not sub_args:
        return None
    with contextlib.suppress(subprocess.SubprocessError, OSError, ValueError, json.JSONDecodeError):
        res = subprocess.run(
            ["hyprctl", "-j", *sub_args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=max(timeout, 2.0),
        )
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    return None


def open_secure_lock(lock_path: Path):
    """Opens a lockfile safely without following symlinks (0600 permissions)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(str(lock_path), flags, 0o600)
    return os.fdopen(fd, "r+", encoding="utf-8")


@contextlib.contextmanager
def file_mutex(lock_path: Path, non_blocking: bool = True):
    """Context manager acquiring an exclusive flock and always closing the FD."""
    lock_f = None
    try:
        lock_f = open_secure_lock(lock_path)
        flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if non_blocking else 0)
        fcntl.flock(lock_f.fileno(), flags)
    except (BlockingIOError, IOError, OSError):
        if lock_f is not None:
            with contextlib.suppress(Exception):
                lock_f.close()
        yield False
        return
    try:
        yield True
    finally:
        with contextlib.suppress(Exception):
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
        with contextlib.suppress(Exception):
            lock_f.close()


def is_flock_held(lock_path: Path) -> bool:
    """Returns True if an exclusive flock is currently held on lock_path."""
    if not lock_path.exists() or lock_path.is_symlink():
        return False
    fd = None
    try:
        fd = os.open(str(lock_path), os.O_RDONLY | os.O_NOFOLLOW)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except (BlockingIOError, IOError, OSError):
            return True
    except OSError:
        return False
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)


def find_pids_by_comm(comm_names: Tuple[str, ...]) -> List[int]:
    """Lists PIDs whose /proc/<pid>/comm matches comm_names without forking."""
    targets = {name.encode("ascii", errors="ignore") for name in comm_names}
    pids: List[int] = []
    with contextlib.suppress(OSError):
        with os.scandir("/proc") as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                with contextlib.suppress(OSError):
                    with open(f"/proc/{entry.name}/comm", "rb") as f:
                        if f.read().strip() in targets:
                            pids.append(int(entry.name))
    return sorted(pids)


def get_lock_state(
    clean_orphans: bool = False,
    hyprlock_running: Optional[bool] = None,
) -> Dict[str, Any]:
    """Detects Hyprland session lock state via /proc comm, flock, and runtime flag."""
    runtime_dir = get_aurora_runtime_dir()
    runtime_flag = runtime_dir / "hypr_locked"
    legacy_flag = Path("/tmp/hypr_locked")
    runtime_inst = runtime_dir / "hypr_lock_instance.lock"
    legacy_inst = Path("/tmp/hypr_lock_instance.lock")

    if hyprlock_running is None:
        hyprlock_running = bool(find_pids_by_comm(("hyprlock",)))

    instance_lock_held = is_flock_held(runtime_inst) or is_flock_held(legacy_inst)
    flag_locked = runtime_flag.exists() or legacy_flag.exists()

    if clean_orphans and flag_locked and not hyprlock_running and not instance_lock_held:
        for flag in (runtime_flag, legacy_flag):
            if flag.exists() and not flag.is_symlink():
                with contextlib.suppress(OSError):
                    flag.unlink()
        flag_locked = False

    locked = bool(hyprlock_running) or instance_lock_held or flag_locked
    return {
        "locked": locked,
        "flag_locked": flag_locked,
        "hyprlock_running": bool(hyprlock_running),
        "instance_lock_held": instance_lock_held,
    }


def _aurora_exe_matches(pid: int, default_on_err: bool = False) -> bool:
    """Checks whether /proc/<pid>/exe points to aurora-wallpaper (handling deleted binary)."""
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
        return exe.removesuffix(" (deleted)").endswith("/aurora-wallpaper")
    except OSError:
        return default_on_err


def is_aurora_proc(pid: int) -> bool:
    """Verifies that PID corresponds to the aurora-wallpaper executable."""
    if _aurora_exe_matches(pid, default_on_err=False):
        return True
    with contextlib.suppress(OSError):
        with open(f"/proc/{pid}/comm", "rb") as f:
            if f.read().strip() in (b"aurora-wallpape", b"aurora-wallpaper"):
                return True
    return False


def get_running_wallpaper_procs() -> List[int]:
    """Lists PIDs of live aurora-wallpaper processes by inspecting /proc/<pid>/comm and exe."""
    return [
        pid
        for pid in find_pids_by_comm(("aurora-wallpape", "aurora-wallpaper"))
        if _aurora_exe_matches(pid, default_on_err=True)
    ]


def spawn_detached(cmd: List[str], cwd: Optional[Path] = None) -> int:
    """Starts a background process isolated from stdio and reaped asynchronously."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    reaper = threading.Thread(target=proc.wait, daemon=True)
    reaper.start()
    return proc.pid


def audit_dotfiles_hardlinks(dotfiles_dir: Path, config_dir: Path) -> Dict[str, Any]:
    """Audits true hard links (same inode, nlink >= 2, no symlinks) for all canonical dotfiles."""
    mismatches: List[str] = []
    symlinks: List[str] = []
    missing: List[str] = []
    checked = 0

    for root, _, files in os.walk(dotfiles_dir):
        if "__pycache__" in Path(root).parts:
            continue
        for fname in sorted(files):
            if fname.endswith(EXCLUDED_DOTFILE_EXTS):
                continue
            src = Path(root) / fname
            rel = src.relative_to(dotfiles_dir)
            rel_str = str(rel)
            dest = config_dir / rel

            if not dest.exists() and not dest.is_symlink():
                missing.append(rel_str)
                continue

            checked += 1
            parent_symlink = None
            curr = dest
            while curr != config_dir and curr != curr.parent:
                if curr.is_symlink():
                    parent_symlink = str(curr)
                    break
                curr = curr.parent

            if parent_symlink:
                symlinks.append(f"{rel_str} (symlink: {parent_symlink})")
                continue

            try:
                src_st = src.stat()
                dst_st = dest.stat()
                if src_st.st_ino != dst_st.st_ino or dst_st.st_nlink < 2:
                    mismatches.append(
                        f"{rel_str} (src_ino={src_st.st_ino}, dst_ino={dst_st.st_ino}, nlink={dst_st.st_nlink})"
                    )
            except OSError as exc:
                missing.append(f"{rel_str} ({exc})")

    ok = len(missing) == 0 and len(mismatches) == 0 and len(symlinks) == 0
    return {
        "ok": ok,
        "all_ok": ok,
        "total_checked": checked,
        "missing": missing,
        "symlinks": symlinks,
        "mismatches": mismatches,
    }
