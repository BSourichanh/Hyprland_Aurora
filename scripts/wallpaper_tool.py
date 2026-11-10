#!/usr/bin/env python3
"""
Wallpaper Tool & Maintenance CLI for Hyprland / Aurora Theme
Unified utility for Aurora Native Wallpaper Engine (C99 Wayland Layer Shell),
dotfiles hard link audits, process management, and IPC event daemon.
"""

import argparse
import contextlib
import fcntl
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mask_generator import generate_blackwall_mask, generate_eye_shine_mask
except ImportError:
    from scripts.mask_generator import generate_blackwall_mask, generate_eye_shine_mask

try:
    from wallpaper_status import display_wallpaper_status
except ImportError:
    from scripts.wallpaper_status import display_wallpaper_status

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESSOURCE_DIR = PROJECT_DIR / "ressource"
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))

LOCAL_BIN_AURORA = Path(os.path.expanduser("~/.local/bin/aurora-wallpaper"))
SRC_AURORA = PROJECT_DIR / "src" / "aurora_wallpaper" / "aurora-wallpaper"

RESTART_LOCK_FILE = "/tmp/wallpaper_restart.lock"
DAEMON_LOCK_FILE = "/tmp/wallpaper_daemon.lock"


@contextlib.contextmanager
def file_mutex(lock_path: str, non_blocking: bool = True):
    """Context manager acquiring an exclusive file lock, yielding True if acquired."""
    try:
        lock_fd = open(lock_path, "w")
        flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if non_blocking else 0)
        fcntl.flock(lock_fd, flags)
    except (BlockingIOError, IOError):
        yield False
        return
    try:
        yield True
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


def get_aurora_binary() -> Path:
    """Returns the executable path for the native C99 wallpaper engine."""
    if LOCAL_BIN_AURORA.exists() and os.access(LOCAL_BIN_AURORA, os.X_OK):
        return LOCAL_BIN_AURORA
    if SRC_AURORA.exists() and os.access(SRC_AURORA, os.X_OK):
        return SRC_AURORA
    return LOCAL_BIN_AURORA


# ============================================================================
# AUDIT DES HARD LINKS (CONFORMITÉ GEMINI.MD)
# ============================================================================

def audit_hardlinks() -> bool:
    """Verifies that all dotfiles match identical inodes in ~/.config/."""
    mismatches, missing, checked = [], [], 0
    for root, _, files in os.walk(DOTFILES_DIR):
        for f in files:
            if f.endswith((".bak", "-bak", ".pyc", ".so")):
                continue
            src = Path(root) / f
            rel = src.relative_to(DOTFILES_DIR)
            dest = CONFIG_DIR / rel
            if not dest.exists():
                missing.append(f"{rel} -> introuvable dans ~/.config/")
                continue
            checked += 1
            if src.stat().st_ino != dest.stat().st_ino:
                mismatches.append(f"{rel} (inode dotfiles: {src.stat().st_ino} != ~/.config: {dest.stat().st_ino})")

    print(f"Audit Hardlinks: {checked} fichiers vérifiés.")
    if missing:
        print(f"✗ Fichiers manquants ({len(missing)}) :\n" + "\n".join(f"  - {m}" for m in missing))
    if mismatches:
        print(f"✗ Ruptures de hard links ({len(mismatches)}) :\n" + "\n".join(f"  - {mm}" for mm in mismatches))
        return False
    print("✓ Tous les hard links sont intacts (inodes identiques).")
    return True


# ============================================================================
# GESTION DU MOTEUR NATIF AURORA (PROCESSUS & COUCHES WAYLAND)
# ============================================================================

def is_aurora_proc(pid: int) -> bool:
    """Verifies that the process executable is actually aurora-wallpaper."""
    with contextlib.suppress(Exception):
        if os.readlink(f"/proc/{pid}/exe").endswith("/aurora-wallpaper"):
            return True
    with contextlib.suppress(Exception):
        if Path(f"/proc/{pid}/comm").read_text().strip().startswith("aurora-wallpape"):
            return True
    return False


def get_running_wallpaper_procs() -> List[int]:
    """Returns list of PIDs for all running aurora-wallpaper instances."""
    res = subprocess.run(["pgrep", "-f", "aurora-wallpaper"], capture_output=True, text=True)
    return [int(p) for p in res.stdout.strip().splitlines() if p.strip().isdigit() and is_aurora_proc(int(p))]


def get_active_layer_wallpaper_screens() -> Dict[str, int]:
    """Returns {monitor_name: pid} for monitors that have an active Wayland layer in Hyprland."""
    active = {}
    with contextlib.suppress(Exception):
        res = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if res.returncode == 0:
            for mon, mon_data in json.loads(res.stdout).items():
                for lvl, items in mon_data.get("levels", {}).items():
                    for item in items:
                        if item.get("namespace") == "aurora-wallpaper":
                            active[mon] = item.get("pid")
    return active


def get_hyprland_connected_screens() -> List[str]:
    """Returns list of currently active screens under Hyprland."""
    with contextlib.suppress(Exception):
        m_res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        if m_res.returncode == 0:
            detected = [m.get("name") for m in json.loads(m_res.stdout) if m.get("name") and not m.get("disabled", False)]
            if detected:
                return detected
    return ["DP-1", "DP-2"]


def is_session_locked() -> bool:
    """Verifies whether session is locked and cleans orphaned lockfiles."""
    if not os.path.exists("/tmp/hypr_locked"):
        return False
    try:
        with open("/tmp/hypr_lock_instance.lock", "r") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        with contextlib.suppress(OSError):
            os.remove("/tmp/hypr_locked")
        return False
    except (BlockingIOError, IOError):
        return True
    except FileNotFoundError:
        with contextlib.suppress(OSError):
            os.remove("/tmp/hypr_locked")
        return False


def terminate_procs(pids: List[int], timeout: float = 0.2):
    """Purge proprement les processus via SIGTERM puis repli immédiat SIGKILL."""
    if not pids:
        return
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, signal.SIGTERM)
    for _ in range(max(1, int(timeout / 0.05))):
        time.sleep(0.05)
        pids = [p for p in pids if is_aurora_proc(p)]
        if not pids:
            return
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, signal.SIGKILL)
    if pids:
        time.sleep(0.05)


def ensure_wallpapers(target_screen: str = None):
    """
    Ensures aurora-wallpaper is actively running and covering connected screens.
    Single-process architecture with shared FBO covering all outputs simultaneously.
    """
    with file_mutex(RESTART_LOCK_FILE) as acquired:
        if not acquired:
            return

        running = get_running_wallpaper_procs()
        active_layers = get_active_layer_wallpaper_screens()
        connected = get_hyprland_connected_screens()

        # Purge proactive de tout processus fantôme sans calque Wayland actif
        active_pids = set(active_layers.values())
        zombies = [pid for pid in running if pid not in active_pids]
        if zombies:
            terminate_procs(zombies, timeout=0.2)
            running = get_running_wallpaper_procs()

        # Si un processus valide tourne et couvre tous les écrans connectés, rien à faire
        if running and all(s in active_layers for s in connected):
            return

        # S'assurer qu'aucun processus résiduel ne persiste avant relance (anti-doublon)
        if running:
            terminate_procs(running, timeout=0.2)

        aurora_bin = get_aurora_binary()
        if not aurora_bin.exists():
            print(f"Erreur : binaire {aurora_bin} introuvable.", file=sys.stderr)
            return

        subprocess.Popen(
            [str(aurora_bin)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(PROJECT_DIR),
        )
        print(f"✓ Moteur aurora-wallpaper démarré (couvre {', '.join(connected)} @ 30 FPS fixes).")


def restart_wallpapers():
    """Safely terminates and restarts aurora-wallpaper across dual monitors."""
    with file_mutex(RESTART_LOCK_FILE) as acquired:
        if not acquired:
            return

        terminate_procs(get_running_wallpaper_procs(), timeout=0.5)

        aurora_bin = get_aurora_binary()
        if not aurora_bin.exists():
            print(f"Erreur : binaire {aurora_bin} introuvable.", file=sys.stderr)
            return

        connected = get_hyprland_connected_screens()
        subprocess.Popen(
            [str(aurora_bin)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(PROJECT_DIR),
        )
        print(f"✓ Moteur aurora-wallpaper relancé sur {', '.join(connected)} [Single-Pass GLES2 @ 30 FPS].")


# ============================================================================
# DÉMON D'ÉCOUTE ÉVÉNEMENTIELLE HYPRLAND (IPC SOCKET2)
# ============================================================================

def get_event_socket_path() -> str:
    """Resolves Hyprland IPC event socket path (.socket2.sock)."""
    runtime_dir, his = os.environ.get("XDG_RUNTIME_DIR"), os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if runtime_dir and his:
        p = os.path.join(runtime_dir, "hypr", his, ".socket2.sock")
        if os.path.exists(p):
            return p
    if runtime_dir and os.path.exists(os.path.join(runtime_dir, "hypr")):
        for d in os.listdir(os.path.join(runtime_dir, "hypr")):
            candidate = os.path.join(runtime_dir, "hypr", d, ".socket2.sock")
            if os.path.exists(candidate):
                return candidate
    return ""


def run_wallpaper_daemon():
    """Continuous background daemon monitoring Hyprland monitor and DPMS events."""
    try:
        lock_fd = open(DAEMON_LOCK_FILE, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
    except (BlockingIOError, IOError):
        print("Le démon Wallpaper Engine est déjà actif.", file=sys.stderr)
        sys.exit(0)

    event_sock_path = get_event_socket_path()
    if not event_sock_path or not os.path.exists(event_sock_path):
        print("Erreur: Socket événement Hyprland introuvable.", file=sys.stderr)
        sys.exit(1)

    def handle_exit(sig, frame):
        with contextlib.suppress(Exception):
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            if os.path.exists(DAEMON_LOCK_FILE):
                os.remove(DAEMON_LOCK_FILE)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    if not is_session_locked():
        ensure_wallpapers()
    print(f"✓ Démon Wallpaper Engine démarré (PID {os.getpid()}), écoute sur {event_sock_path}...")
    sys.stdout.flush()

    debounce_delay = 0.4
    pending_ensure = 0.0
    MONITOR_EVENTS = ("monitoradded", "monitorremoved", "configreloaded", "dpms")

    while True:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(event_sock_path)
            s.setblocking(False)
            buf = ""
            while True:
                now = time.time()
                timeout = 2.0
                if pending_ensure > 0.0:
                    timeout = min(timeout, max(0.0, pending_ensure - now))

                rlist, _, _ = select.select([s], [], [], timeout)
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
                        ev_type = line.split(">>")[0]
                        if not is_session_locked() and any(ev_type.startswith(ev) for ev in MONITOR_EVENTS):
                            pending_ensure = time.time() + debounce_delay

                now_check = time.time()
                if pending_ensure > 0.0:
                    if now_check >= pending_ensure:
                        pending_ensure = 0.0
                        if not is_session_locked():
                            ensure_wallpapers()
                elif not is_session_locked():
                    active_layers = get_active_layer_wallpaper_screens()
                    connected = get_hyprland_connected_screens()
                    if any(scr not in active_layers for scr in connected):
                        ensure_wallpapers()

            s.close()
        except Exception:
            time.sleep(1.0)
            event_sock_path = get_event_socket_path()
            if not event_sock_path or not os.path.exists(event_sock_path):
                time.sleep(2.0)


# ============================================================================
# ÉTAT ET MONITORING SYSTÈME
# ============================================================================

def show_status():
    """Displays running state of aurora-wallpaper, monitors, and Wayland layers."""
    display_wallpaper_status(DAEMON_LOCK_FILE, get_running_wallpaper_procs)


# ============================================================================
# POINT D'ENTRÉE CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Aurora Wallpaper Engine & Maintenance CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Afficher l'état du moteur aurora-wallpaper et couches Wayland")
    sub.add_parser("mask", help="Régénérer le masque Blackwall vectoriel haute fidélité")
    sub.add_parser("check-links", help="Vérifier la stricte intégrité des hard links dotfiles")
    sub.add_parser("restart", help="Redémarrer proprement aurora-wallpaper")
    sub.add_parser("daemon", help="Lancer le démon d'écoute hotplug IPC")
    p_ens = sub.add_parser("ensure", help="Garantir la présence de aurora-wallpaper")
    p_ens.add_argument("screen", nargs="?", help="Optionnel pour compatibilité")

    args = parser.parse_args()
    if args.command == "status":
        show_status()
    elif args.command == "daemon":
        run_wallpaper_daemon()
    elif args.command == "mask":
        generate_blackwall_mask()
        generate_eye_shine_mask()
    elif args.command == "check-links":
        sys.exit(0 if audit_hardlinks() else 1)
    elif args.command == "ensure":
        ensure_wallpapers(target_screen=args.screen)
    elif args.command == "restart":
        restart_wallpapers()


if __name__ == "__main__":
    main()
