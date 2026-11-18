#!/usr/bin/env python3
"""
Status & Diagnostic Inspector for Aurora Wallpaper Engine
Displays running state of aurora-wallpaper, CPU/RAM, GPU frequency, and Wayland layer levels.
"""

import contextlib
import glob
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional, Union

try:
    from aurora_runtime import (
        get_aurora_runtime_dir,
        get_lock_state,
        get_running_wallpaper_procs,
        is_flock_held,
    )
except ImportError:
    from scripts.aurora_runtime import (
        get_aurora_runtime_dir,
        get_lock_state,
        get_running_wallpaper_procs,
        is_flock_held,
    )


def _detect_daemon_pid(daemon_lock_file: Union[str, Path]) -> Optional[int]:
    """Resolves active wallpaper daemon PID verifying flock and /proc cmdline."""
    candidates = [Path(daemon_lock_file), Path("/tmp/wallpaper_daemon.lock")]
    for lock_path in candidates:
        if not lock_path.exists() or lock_path.is_symlink():
            continue
        try:
            val = lock_path.read_text(encoding="utf-8").strip()
            if not val.isdigit():
                continue
            pid = int(val)
            cmdline_file = Path(f"/proc/{pid}/cmdline")
            if not cmdline_file.exists():
                continue
            cmdline = cmdline_file.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
            if "wallpaper_tool.py" in cmdline and (is_flock_held(lock_path) or lock_path.parent == Path("/tmp")):
                return pid
        except Exception:
            continue
    return None


def _get_clk_tck() -> int:
    """Safely retrieves kernel clock ticks per second (SC_CLK_TCK)."""
    try:
        val = os.sysconf("SC_CLK_TCK")
        return int(val) if val > 0 else 100
    except (ValueError, OSError, AttributeError):
        return 100


def display_wallpaper_status(
    daemon_lock_file: Union[str, Path],
    get_running_procs: Callable[[], List[int]],
) -> None:
    """Displays running state of aurora-wallpaper, monitors, and Wayland layers."""
    locked = get_lock_state()["locked"]
    cadence_label = "60 FPS (session verrouillée)" if locked else "30 FPS fixes"

    print("=== Aurora Wallpaper Engine (Micro-Moteur Natif Wayland C99) ===")
    print("  • Architecture : Single-Pass GLSL + FBO Partagé (Mutualisé Multi-Écrans)")
    print(f"  • Cadence Cible : {cadence_label}")

    daemon_pid = _detect_daemon_pid(daemon_lock_file)
    print(f"=== Démon Hotplug IPC : {'Actif [PID ' + str(daemon_pid) + ']' if daemon_pid else 'Inactif'} ===")

    print("=== État du Processus aurora-wallpaper ===")
    procs = get_running_procs()
    if not procs:
        print("✗ Aucun processus aurora-wallpaper actif.")
    else:
        clk_tck = _get_clk_tck()
        for pid in procs:
            total_rss = 0.0
            total_cpu = 0.0
            stat_file = Path(f"/proc/{pid}/status")
            if stat_file.exists():
                with contextlib.suppress(Exception):
                    for line in stat_file.read_text(encoding="utf-8").splitlines():
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                total_rss = int(parts[1]) / 1024.0
                                break

            with contextlib.suppress(Exception):
                def read_cpu() -> int:
                    with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
                        fields = f.read().split()
                        return int(fields[13]) + int(fields[14])

                t0_cpu = read_cpu()
                t0_time = time.monotonic()
                time.sleep(0.3)
                t1_cpu = read_cpu()
                dt = time.monotonic() - t0_time
                if dt > 0:
                    total_cpu = ((t1_cpu - t0_cpu) / clk_tck / dt) * 100.0

            total_global = (total_cpu / ((os.cpu_count() or 1) * 100.0)) * 100.0
            print(f"✓ PID {pid} : CPU: {total_cpu:.1f}% ({total_global:.1f}% global) | RAM: {total_rss:.1f} Mo")

        for card in sorted(glob.glob("/sys/class/drm/card*/gt_act_freq_mhz")):
            with contextlib.suppress(Exception):
                print(f"  • Fréquence GPU active : {Path(card).read_text(encoding='utf-8').strip()} MHz")
                break

    with contextlib.suppress(Exception):
        layers = subprocess.run(
            ["hyprctl", "layers", "-j"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if layers.returncode == 0 and layers.stdout.strip():
            print("\n=== Couches Wayland Détectées (Hyprland) ===")
            layer_names = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}
            for mon, mon_data in json.loads(layers.stdout).items():
                active = [
                    f"{layer_names.get(str(lvl), f'Lvl{lvl}')}:{it.get('namespace', '?')}[pid:{it.get('pid', '?')}]"
                    for lvl, items in mon_data.get("levels", {}).items()
                    for it in items
                ]
                print(f"  • {mon} : {' | '.join(active) if active else 'Aucune'}")


if __name__ == "__main__":
    lock_file = get_aurora_runtime_dir() / "wallpaper_daemon.lock"
    display_wallpaper_status(lock_file, get_running_wallpaper_procs)
