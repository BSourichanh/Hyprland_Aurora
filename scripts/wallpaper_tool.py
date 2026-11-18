#!/usr/bin/env python3
"""
Wallpaper Tool & Maintenance CLI for Hyprland / Aurora Theme
Unified utility for Aurora Native Wallpaper Engine (C99 Wayland Layer Shell),
dotfiles hard link audits, process management, and IPC event daemon.
"""

import argparse
import contextlib
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from aurora_runtime import (
        audit_dotfiles_hardlinks,
        file_mutex,
        find_pids_by_comm,
        get_aurora_runtime_dir,
        get_lock_state,
        get_running_wallpaper_procs,
        hypr_socket_json,
        is_aurora_proc,
        spawn_detached,
    )
    from mask_generator import generate_blackwall_mask, generate_eye_shine_mask
    from wallpaper_daemon import run_wallpaper_daemon
    from wallpaper_status import display_wallpaper_status
except ImportError:
    from scripts.aurora_runtime import (
        audit_dotfiles_hardlinks,
        file_mutex,
        find_pids_by_comm,
        get_aurora_runtime_dir,
        get_lock_state,
        get_running_wallpaper_procs,
        hypr_socket_json,
        is_aurora_proc,
        spawn_detached,
    )
    from scripts.mask_generator import generate_blackwall_mask, generate_eye_shine_mask
    from scripts.wallpaper_daemon import run_wallpaper_daemon
    from scripts.wallpaper_status import display_wallpaper_status

PROJECT_DIR = Path(__file__).resolve().parent.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))

LOCAL_BIN_AURORA = Path(os.path.expanduser("~/.local/bin/aurora-wallpaper"))
SRC_AURORA = PROJECT_DIR / "src" / "aurora_wallpaper" / "aurora-wallpaper"

RUNTIME_DIR = get_aurora_runtime_dir()
RESTART_LOCK_FILE = RUNTIME_DIR / "wallpaper_restart.lock"
DAEMON_LOCK_FILE = RUNTIME_DIR / "wallpaper_daemon.lock"


def get_aurora_binary() -> Path:
    """Returns the executable path for the native C99 wallpaper engine."""
    if LOCAL_BIN_AURORA.exists() and os.access(LOCAL_BIN_AURORA, os.X_OK):
        return LOCAL_BIN_AURORA
    if SRC_AURORA.exists() and os.access(SRC_AURORA, os.X_OK):
        return SRC_AURORA
    return LOCAL_BIN_AURORA


def audit_hardlinks() -> bool:
    """Verifies true hard links (same inode, nlink >= 2, no symlinks) for all canonical dotfiles."""
    res = audit_dotfiles_hardlinks(DOTFILES_DIR, CONFIG_DIR)
    print(f"Audit Hardlinks: {res['total_checked']} fichiers vérifiés.")
    if res["missing"]:
        print(f"✗ Fichiers manquants ({len(res['missing'])}) :\n" + "\n".join(f"  - {m}" for m in res["missing"]))
    if res["symlinks"]:
        print(f"✗ Symlinks détectés ({len(res['symlinks'])}) :\n" + "\n".join(f"  - {s}" for s in res["symlinks"]))
    if res["mismatches"]:
        print(f"✗ Ruptures de hard links ({len(res['mismatches'])}) :\n" + "\n".join(f"  - {mm}" for mm in res["mismatches"]))
    if res["ok"]:
        print("✓ Tous les hard links sont intacts (inodes identiques, zéro symlink).")
    return res["ok"]


def get_active_layer_wallpaper_screens() -> Dict[str, int]:
    """Returns {monitor_name: pid} for monitors that have an active Wayland layer in Hyprland."""
    active: Dict[str, int] = {}
    layers_data = hypr_socket_json("j/layers", timeout=1.0)
    if isinstance(layers_data, dict):
        for mon, mon_data in layers_data.items():
            if not isinstance(mon_data, dict):
                continue
            for _, items in mon_data.get("levels", {}).items():
                for item in items:
                    if isinstance(item, dict) and item.get("namespace") == "aurora-wallpaper":
                        active[mon] = item.get("pid")
    return active


def get_hyprland_connected_screens() -> List[str]:
    """Returns list of currently active screens under Hyprland."""
    monitors_data = hypr_socket_json("j/monitors", timeout=1.0)
    if isinstance(monitors_data, list):
        detected = [
            m.get("name")
            for m in monitors_data
            if isinstance(m, dict) and m.get("name") and not m.get("disabled", False)
        ]
        if detected:
            return detected
    return ["DP-1", "DP-2"]


def is_session_locked() -> bool:
    """Verifies whether session is locked and cleans orphaned lockfiles."""
    return bool(get_lock_state(clean_orphans=True)["locked"])


def terminate_procs(pids: List[int], timeout: float = 0.2) -> None:
    """Gracefully terminates aurora-wallpaper PIDs via SIGTERM then SIGKILL fallback."""
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


def _stop_redundant_swaybg(
    required_screens: Optional[List[str]] = None,
    wait_timeout: float = 0.0,
) -> bool:
    """Stops redundant swaybg only after aurora-wallpaper is active on all connected monitors."""
    swaybg_pids = find_pids_by_comm(("swaybg",))
    if not swaybg_pids:
        return False

    screens = required_screens or get_hyprland_connected_screens()
    deadline = time.monotonic() + max(0.0, wait_timeout)
    covered = False
    while True:
        running = set(get_running_wallpaper_procs())
        if running:
            active_layers = get_active_layer_wallpaper_screens()
            if screens and all(active_layers.get(scr) in running for scr in screens):
                covered = True
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.05)

    if not covered:
        return False

    stopped = False
    for pid in swaybg_pids:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, signal.SIGTERM)
            stopped = True
    return stopped


def ensure_wallpapers(target_screen: Optional[str] = None) -> None:
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
        required = [target_screen] if (target_screen and target_screen in connected) else connected

        active_pids = set(active_layers.values())
        zombies = [pid for pid in running if pid not in active_pids]
        if zombies:
            time.sleep(0.25)
            active_layers = get_active_layer_wallpaper_screens()
            active_pids = set(active_layers.values())
            running = get_running_wallpaper_procs()
            zombies = [pid for pid in running if pid not in active_pids]
            if zombies:
                terminate_procs(zombies, timeout=0.2)
                running = get_running_wallpaper_procs()

        if running and all(s in active_layers for s in required):
            _stop_redundant_swaybg(connected)
            return

        # Laisser une fenêtre brève au hotplug natif Wayland si le processus valide tourne déjà
        if running and any(s in active_layers for s in connected):
            time.sleep(0.3)
            active_layers = get_active_layer_wallpaper_screens()
            if all(s in active_layers for s in required):
                _stop_redundant_swaybg(connected)
                return

        if running:
            terminate_procs(running, timeout=0.2)

        aurora_bin = get_aurora_binary()
        if not aurora_bin.exists():
            print(f"Erreur : binaire {aurora_bin} introuvable.", file=sys.stderr)
            return

        spawn_detached([str(aurora_bin)], cwd=PROJECT_DIR)
        _stop_redundant_swaybg(connected, wait_timeout=1.5)
        print(f"✓ Moteur aurora-wallpaper démarré (couvre {', '.join(required)} @ 30 FPS fixes).")


def restart_wallpapers() -> None:
    """Safely terminates and restarts aurora-wallpaper across connected monitors."""
    with file_mutex(RESTART_LOCK_FILE) as acquired:
        if not acquired:
            return

        terminate_procs(get_running_wallpaper_procs(), timeout=0.5)

        aurora_bin = get_aurora_binary()
        if not aurora_bin.exists():
            print(f"Erreur : binaire {aurora_bin} introuvable.", file=sys.stderr)
            return

        connected = get_hyprland_connected_screens()
        spawn_detached([str(aurora_bin)], cwd=PROJECT_DIR)
        _stop_redundant_swaybg(connected, wait_timeout=1.5)
        print(f"✓ Moteur aurora-wallpaper relancé sur {', '.join(connected)} [Single-Pass GLES2 @ 30 FPS].")


def show_status() -> None:
    """Displays running state of aurora-wallpaper, monitors, and Wayland layers."""
    display_wallpaper_status(DAEMON_LOCK_FILE, get_running_wallpaper_procs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aurora Wallpaper Engine & Maintenance CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Afficher l'état du moteur aurora-wallpaper et couches Wayland")
    sub.add_parser("mask", help="Régénérer le masque Blackwall vectoriel haute fidélité")
    sub.add_parser("check-links", help="Vérifier la stricte intégrité des hard links dotfiles")
    sub.add_parser("restart", help="Redémarrer proprement aurora-wallpaper")
    sub.add_parser("daemon", help="Lancer le démon d'écoute hotplug IPC")
    p_ens = sub.add_parser("ensure", help="Garantir la présence de aurora-wallpaper")
    p_ens.add_argument("screen", nargs="?", help="Écran cible optionnel (ex: DP-1, DP-2)")

    args = parser.parse_args()
    if args.command == "status":
        show_status()
    elif args.command == "daemon":
        run_wallpaper_daemon(
            DAEMON_LOCK_FILE,
            ensure_wallpapers,
            get_active_layer_wallpaper_screens,
            get_hyprland_connected_screens,
        )
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
