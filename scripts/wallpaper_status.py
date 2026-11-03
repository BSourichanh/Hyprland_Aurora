#!/usr/bin/env python3
"""
Status & Diagnostic Inspector for Aurora Wallpaper Engine
Displays running state of aurora-wallpaper, CPU/RAM, GPU frequency, and Wayland layer levels.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, List


def display_wallpaper_status(
    daemon_lock_file: str,
    get_running_procs: Callable[[], List[int]],
):
    """Displays running state of aurora-wallpaper, monitors, and Wayland layers."""
    print("=== Aurora Wallpaper Engine (Micro-Moteur Natif Wayland C99) ===")
    print("  • Architecture : Single-Pass GLSL + FBO Partagé 1920x1080 (Mutualisé Multi-Écrans)")
    print("  • Cadence Cible : 30 FPS fixes")

    daemon_pid = None
    if os.path.exists(daemon_lock_file):
        try:
            val = Path(daemon_lock_file).read_text().strip()
            if val.isdigit() and os.path.exists(f"/proc/{val}"):
                daemon_pid = int(val)
        except Exception:
            pass
    print(f"=== Démon Hotplug IPC : {'Actif [PID ' + str(daemon_pid) + ']' if daemon_pid else 'Inactif'} ===")

    print("=== État du Processus aurora-wallpaper ===")
    procs = get_running_procs()
    if not procs:
        print("✗ Aucun processus aurora-wallpaper actif.")
    else:
        for pid in procs:
            total_rss = 0.0
            total_cpu = 0.0
            stat_file = Path(f"/proc/{pid}/status")
            if stat_file.exists():
                try:
                    for line in stat_file.read_text().splitlines():
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                total_rss = int(parts[1]) / 1024.0
                except Exception:
                    pass

            try:
                def read_cpu():
                    with open(f"/proc/{pid}/stat", "r") as f:
                        fields = f.read().split()
                        return int(fields[13]) + int(fields[14])
                t0_cpu = read_cpu()
                t0_time = time.time()
                time.sleep(0.1)
                t1_cpu = read_cpu()
                dt = time.time() - t0_time
                clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 100)) or 100
                if dt > 0:
                    total_cpu = ((t1_cpu - t0_cpu) / clk_tck / dt) * 100.0
            except Exception:
                pass

            total_global = (total_cpu / ((os.cpu_count() or 1) * 100.0)) * 100.0
            print(f"✓ PID {pid} : CPU: {total_cpu:.1f}% ({total_global:.1f}% global) | RAM: {total_rss:.1f} Mo")

        for card in ("/sys/class/drm/card1/gt_act_freq_mhz", "/sys/class/drm/card0/gt_act_freq_mhz"):
            if Path(card).exists():
                try:
                    print(f"  • Fréquence GPU active : {Path(card).read_text().strip()} MHz")
                    break
                except Exception:
                    pass

    try:
        layers = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if layers.returncode == 0:
            print("\n=== Couches Wayland Détectées (Hyprland) ===")
            layer_names = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}
            for mon, mon_data in json.loads(layers.stdout).items():
                active = [
                    f"{layer_names.get(str(lvl), f'Lvl{lvl}')}:{it.get('namespace', '?')}[pid:{it.get('pid', '?')}]"
                    for lvl, items in mon_data.get("levels", {}).items()
                    for it in items
                ]
                print(f"  • {mon} : {' | '.join(active) if active else 'Aucune'}")
    except Exception:
        pass
