#!/usr/bin/env python3
"""
Wallpaper Tool & Maintenance CLI for Hyprland / Aurora Theme
Unified utility for Aurora Native Wallpaper Engine (C99 Wayland Layer Shell),
subpixel mask generation, dotfiles hard link audits, and process management.
"""

import argparse
import contextlib
import fcntl
import json
import math
import os
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None
    ImageFilter = None


@contextlib.contextmanager
def file_mutex(lock_path: str, non_blocking: bool = True):
    """Context manager acquiring an exclusive file lock, yielding True if acquired."""
    try:
        lock_fd = open(lock_path, "w")
        flags = fcntl.LOCK_EX
        if non_blocking:
            flags |= fcntl.LOCK_NB
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


PROJECT_DIR = Path(__file__).resolve().parent.parent
RESSOURCE_DIR = PROJECT_DIR / "ressource"
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
LOCAL_BIN_AURORA = Path(os.path.expanduser("~/.local/bin/aurora-wallpaper"))
SRC_AURORA = PROJECT_DIR / "src" / "aurora_wallpaper" / "aurora-wallpaper"

RESTART_LOCK_FILE = "/tmp/wallpaper_restart.lock"
DAEMON_LOCK_FILE = "/tmp/wallpaper_daemon.lock"


def get_aurora_binary() -> Path:
    """Returns the executable path for aurora-wallpaper."""
    if LOCAL_BIN_AURORA.exists() and os.access(LOCAL_BIN_AURORA, os.X_OK):
        return LOCAL_BIN_AURORA
    if SRC_AURORA.exists() and os.access(SRC_AURORA, os.X_OK):
        return SRC_AURORA
    return LOCAL_BIN_AURORA


# ============================================================================
# 1. MATHEMATICAL SUBPIXEL MASK GENERATION
# ============================================================================

def generate_blackwall_mask(
    input_png: Path = RESSOURCE_DIR / "lucy.png",
    output_png: Path = RESSOURCE_DIR / "blackwall" / "blackwall_mask.png",
):
    """
    Generates a subpixel anti-aliased mask from Lucy artwork using mathematical
    gradient decomposition and BFS propagation, preserving hair strands while
    eliminating trapped background and opaque patches.
    """
    if Image is None:
        sys.exit("Erreur : Pillow (PIL) est requis pour générer le masque.")

    im = Image.open(input_png)
    w, h = im.size

    # 1. Calcul de la déviation euclidienne par rapport au fond théorique
    diffs = [0.0] * (w * h)
    for y in range(h):
        by_r = y * 170.0 / 1079.0
        by_b = y * 88.0 / 1079.0
        for x in range(w):
            r, g, b = im.getpixel((x, y))
            d = math.sqrt((r - by_r) ** 2 + (g - 0.0) ** 2 + (b - by_b) ** 2)
            diffs[y * w + x] = d

    # 2. Ensemencement global sur tout pixel avec D <= 1.8 (fond garanti à 100%)
    visited = bytearray(w * h)
    q = deque()
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if diffs[idx] <= 1.8:
                visited[idx] = 1
                q.append((x, y))

    # 3. Propagation BFS à travers l'anti-aliasing (s'arrête avant le premier plan à D >= 18.0)
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h:
                nidx = ny * w + nx
                if not visited[nidx]:
                    if diffs[nidx] < 18.0:
                        visited[nidx] = 1
                        q.append((nx, ny))

    # 4. Reconstruction de l'opacité sous-pixel par projection linéaire
    mask = Image.new("L", (w, h), 0)
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if visited[idx]:
                d = diffs[idx]
                if d <= 1.8:
                    val = 255
                else:
                    t = (d - 1.8) / (18.0 - 1.8)
                    val = int(round((1.0 - t) * 255.0))
                if val > 0:
                    mask.putpixel((x, y), val)

    # 5. Filtrage morphologique des composantes connexes parasites
    mask_arr = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if mask.getpixel((x, y)) > 0:
                mask_arr[y * w + x] = 1

    visited_cc = bytearray(w * h)
    components = []
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if mask_arr[idx] and not visited_cc[idx]:
                comp = []
                cq = deque([(x, y)])
                visited_cc[idx] = 1
                comp.append((x, y))
                while cq:
                    curr_x, curr_y = cq.popleft()
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nx, ny = curr_x + dx, curr_y + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            nidx = ny * w + nx
                            if mask_arr[nidx] and not visited_cc[nidx]:
                                visited_cc[nidx] = 1
                                cq.append((nx, ny))
                                comp.append((nx, ny))
                components.append(comp)

    for comp in components:
        xs = [p[0] for p in comp]
        ys = [p[1] for p in comp]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        is_slit = (min_x >= 1340 and max_x <= 1490 and min_y >= 650 and max_y <= 1010)
        is_noise = len(comp) < 10
        if is_slit or is_noise:
            for x, y in comp:
                mask.putpixel((x, y), 0)

    # 6. Intégration des deux ouvertures entre les doigts
    for y in range(786, 814):
        for x in range(984, 1004):
            r, g, b = im.getpixel((x, y))
            diff = r - g
            if diff >= 75:
                m = 255
            elif diff <= 20:
                m = 0
            else:
                t = (diff - 20.0) / (75.0 - 20.0)
                m = int(t * t * (3.0 - 2.0 * t) * 255)
            if m > mask.getpixel((x, y)):
                mask.putpixel((x, y), m)

    for y in range(896, 934):
        for x in range(878, 938):
            r, g, b = im.getpixel((x, y))
            diff = r - g
            if diff >= 75:
                m = 255
            elif diff <= 20:
                m = 0
            else:
                t = (diff - 20.0) / (75.0 - 20.0)
                m = int(t * t * (3.0 - 2.0 * t) * 255)
            if m > mask.getpixel((x, y)):
                mask.putpixel((x, y), m)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    wave_png = RESSOURCE_DIR / "waterwaves_mask.png"
    flow_png = RESSOURCE_DIR / "shake_flowmask.png"
    if wave_png.exists() and flow_png.exists():
        wave_im = Image.open(wave_png).convert("L")
        if wave_im.size != (w, h):
            wave_im = wave_im.resize((w, h), Image.Resampling.LANCZOS)
        flow_im = Image.open(flow_png).convert("RGB")
        if flow_im.size != (w, h):
            flow_im = flow_im.resize((w, h), Image.Resampling.LANCZOS)
        flow_r, flow_g, _ = flow_im.split()
        comp_mask = Image.merge("RGBA", (mask, flow_g, flow_r, wave_im))
        comp_mask.save(output_png)
    else:
        mask.save(output_png)
    print(f"✓ Masque Blackwall 4-Canaux (Cutout + FlowMap + Ondulations) généré : {output_png} ({w}x{h})")


def generate_eye_shine_mask(
    input_png: Path = RESSOURCE_DIR / "lucy.png",
    output_png: Path = RESSOURCE_DIR / "materials" / "masks" / "shine_downsample2_mask_b309bcdf.png",
):
    """Génère le masque vectoriel de la pupille avec anti-aliasing sous-pixel."""
    if Image is None or ImageFilter is None:
        sys.exit("Erreur : Pillow (PIL) est requis pour générer le masque.")

    im = Image.open(input_png)
    w, h = im.size
    mask = Image.new("L", (w, h), 0)

    top_eyelid_bottom = {}
    for x in range(1085, 1180):
        last_lid = 280
        for y in range(275, 325):
            r, g, b = im.getpixel((x, y))[:3]
            if r < 55 and g < 52 and b < 72:
                last_lid = y
        top_eyelid_bottom[x] = last_lid

    for y in range(285, 360):
        for x in range(1090, 1180):
            if y <= top_eyelid_bottom.get(x, 280):
                continue
            r, g, b = im.getpixel((x, y))[:3]
            if r < 50 and g < 46 and b < 64 and y > 330:
                continue
            if x < 1100 and y > 343:
                continue
            if x > 1172:
                continue
            is_cyan = (b - r > 35) and (g - r > 15) and (b > 110)
            is_magenta = (r - g > 20) and (b - g > 10) and (r > 85)
            is_pupil = (r < 100) and (g < 80) and (b < 105) and (r > 35) and (b > 40) and (x >= 1110) and (x <= 1142) and (y >= 300) and (y <= 328)
            is_specular = (r > 180) and (g > 180) and (b > 180) and (x >= 1130) and (x <= 1170) and (y <= 325)
            if is_cyan or is_magenta or is_pupil or is_specular:
                mask.putpixel((x, y), 255)

    for y in range(390, 440):
        for x in range(730, 788):
            r, g, b = im.getpixel((x, y))[:3]
            is_cyan = (b - r > 25) and (g - r > 12) and (b > 85)
            is_magenta = (r - g > 18) and (b - g > 8) and (r > 75)
            is_specular = (r > 175) and (g > 175) and (b > 175) and (x > 755) and (y < 425)
            if (is_cyan or is_magenta or is_specular) and not (r < 38 and g < 38 and b < 48):
                mask.putpixel((x, y), 255)

    mask_closed = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    mask_smooth = mask_closed.filter(ImageFilter.GaussianBlur(radius=0.7))
    mask_540 = mask_smooth.resize((960, 540), Image.Resampling.LANCZOS)

    output_png.parent.mkdir(parents=True, exist_ok=True)
    mask_540.save(output_png)
    print(f"✓ Masque pupille généré : {output_png} (960x540)")


# ============================================================================
# 2. AUDIT DES HARD LINKS (CONFORMITÉ GEMINI.MD)
# ============================================================================

def audit_hardlinks() -> bool:
    """Verifies that all dotfiles match identical inodes in ~/.config/."""
    mismatches = []
    missing = []
    checked = 0

    for root, _, files in os.walk(DOTFILES_DIR):
        for f in files:
            if f.endswith((".bak", "-bak", ".pyc", ".so")):
                continue
            dot_path = Path(root) / f
            rel = dot_path.relative_to(DOTFILES_DIR)
            conf_path = CONFIG_DIR / rel

            if not conf_path.exists():
                missing.append(rel)
                continue

            checked += 1
            if dot_path.stat().st_ino != conf_path.stat().st_ino:
                mismatches.append(rel)

    print(f"Audit Hardlinks: {checked} fichiers vérifiés.")
    if not mismatches and not missing:
        print("✓ Tous les hard links sont intacts (inodes identiques).")
        return True

    if missing:
        print(f"✗ Fichiers manquants dans ~/.config : {missing}")
    if mismatches:
        print(f"✗ Inodes divergents (liens rompus) : {mismatches}")
    return False


# ============================================================================
# 3. GESTION DU MOTEUR NATIF AURORA (PROCESSUS & COUCHES WAYLAND)
# ============================================================================

def is_aurora_proc(pid: int) -> bool:
    """Verifies that the process executable is actually aurora-wallpaper."""
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
        if exe.endswith("/aurora-wallpaper"):
            return True
    except Exception:
        pass
    try:
        comm = Path(f"/proc/{pid}/comm").read_text().strip()
        if comm.startswith("aurora-wallpape"):
            return True
    except Exception:
        pass
    return False


def get_running_wallpaper_procs() -> List[int]:
    """Returns list of PIDs for all running aurora-wallpaper instances."""
    procs = []
    res = subprocess.run(["pgrep", "-f", "aurora-wallpaper"], capture_output=True, text=True)
    for p in res.stdout.strip().splitlines():
        if p.strip() and p.isdigit():
            pid = int(p)
            if is_aurora_proc(pid):
                procs.append(pid)
    return procs


def get_active_layer_wallpaper_screens() -> Dict[str, int]:
    """Returns {monitor_name: pid} for monitors that have an active Wayland layer in Hyprland."""
    active = {}
    try:
        res = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for mon, mon_data in data.items():
                for lvl, items in mon_data.get("levels", {}).items():
                    for item in items:
                        if item.get("namespace") == "aurora-wallpaper":
                            active[mon] = item.get("pid")
    except Exception:
        pass
    return active


def get_hyprland_connected_screens() -> List[str]:
    """Returns list of currently active screens under Hyprland."""
    try:
        m_res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
        if m_res.returncode == 0:
            m_data = json.loads(m_res.stdout)
            detected = [m.get("name") for m in m_data if m.get("name")]
            if detected:
                return detected
    except Exception:
        pass
    return ["DP-1", "DP-2"]


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

        # Si le processus tourne et couvre tous les écrans connectés, rien à faire
        if running and all(s in active_layers for s in connected):
            return

        # S'il y a un processus fantôme sans couche active, le nettoyer
        if running and not active_layers:
            for pid in running:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            time.sleep(0.1)

        aurora_bin = get_aurora_binary()
        if not aurora_bin.exists():
            print(f"Erreur : binaire {aurora_bin} introuvable. Compilez-le avec 'make -C src/aurora_wallpaper install'.", file=sys.stderr)
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

        procs = get_running_wallpaper_procs()
        for pid in procs:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

        for _ in range(15):
            if not get_running_wallpaper_procs():
                break
            time.sleep(0.05)

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
# 4. DÉMON D'ÉCOUTE HOTPLUG IPC HYPRLAND
# ============================================================================

def get_event_socket_path() -> str:
    """Discovers the active Hyprland event socket path (.socket2.sock)."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        return ""
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if his:
        sock = os.path.join(runtime_dir, "hypr", his, ".socket2.sock")
        if os.path.exists(sock):
            return sock
    hypr_dir = os.path.join(runtime_dir, "hypr")
    if os.path.isdir(hypr_dir):
        for entry in os.listdir(hypr_dir):
            candidate = os.path.join(hypr_dir, entry, ".socket2.sock")
            if os.path.exists(candidate):
                return candidate
    return ""


def run_wallpaper_daemon():
    """
    Continuous background daemon monitoring Hyprland monitor events (.socket2.sock).
    Automatically restores aurora-wallpaper on reconnected/woken monitors.
    """
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
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            if os.path.exists(DAEMON_LOCK_FILE):
                os.remove(DAEMON_LOCK_FILE)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Initialisation au démarrage : garantir la présence sur les écrans connectés
    ensure_wallpapers()

    print(f"✓ Démon Wallpaper Engine démarré (PID {os.getpid()}), écoute sur {event_sock_path}...")
    sys.stdout.flush()

    debounce_delay = 0.4
    pending_ensure = 0.0

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
                        if ev_type.startswith("monitoradded") or ev_type == "configreloaded":
                            pending_ensure = time.time() + debounce_delay

                now_check = time.time()
                if pending_ensure > 0.0 and now_check >= pending_ensure:
                    pending_ensure = 0.0
                    ensure_wallpapers()
                elif not os.path.exists("/tmp/hypr_locked"):
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
# 5. DIAGNOSTIC ÉTAT & PERFORMANCES
# ============================================================================

def show_status():
    """Displays running state of aurora-wallpaper, monitors, and Wayland layers."""
    print("=== Aurora Wallpaper Engine (Micro-Moteur Natif Wayland C99) ===")
    print("  • Architecture : Single-Pass GLSL + FBO Partagé 1920x1080 (Mutualisé Multi-Écrans)")
    print("  • Cadence Cible : 30 FPS fixes")

    daemon_pid = None
    if os.path.exists(DAEMON_LOCK_FILE):
        try:
            with open(DAEMON_LOCK_FILE, "r") as f:
                content = f.read().strip()
                if content.isdigit():
                    d_pid = int(content)
                    if os.path.exists(f"/proc/{d_pid}"):
                        daemon_pid = d_pid
        except Exception:
            pass
    if daemon_pid:
        print(f"=== Démon Hotplug IPC : Actif [PID {daemon_pid}] ===")
    else:
        print("=== Démon Hotplug IPC : Inactif ===")

    print("=== État du Processus aurora-wallpaper ===")
    procs = get_running_wallpaper_procs()
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
                t1_time = time.time()
                clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 100)) or 100
                dt = t1_time - t0_time
                if dt > 0:
                    total_cpu = ((t1_cpu - t0_cpu) / clk_tck / dt) * 100.0
            except Exception:
                pass

            cpu_count = os.cpu_count() or 1
            total_cores_pct = cpu_count * 100.0
            total_global = (total_cpu / total_cores_pct) * 100.0
            print(f"✓ PID {pid} : CPU: {total_cpu:.1f}% ({total_global:.1f}% global) | RAM: {total_rss:.1f} Mo")

        gpu_freq_file = Path("/sys/class/drm/card1/gt_act_freq_mhz")
        if not gpu_freq_file.exists():
            gpu_freq_file = Path("/sys/class/drm/card0/gt_act_freq_mhz")
        if gpu_freq_file.exists():
            try:
                freq = gpu_freq_file.read_text().strip()
                print(f"  • Fréquence GPU active : {freq} MHz")
            except Exception:
                pass

    # Vérification des couches Hyprland
    try:
        layers = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True)
        if layers.returncode == 0:
            data = json.loads(layers.stdout)
            print("\n=== Couches Wayland Détectées (Hyprland) ===")
            layer_names = {"0": "Background", "1": "Bottom", "2": "Top", "3": "Overlay"}
            for mon, mon_data in data.items():
                active_layers = []
                for lvl_num, lvl_items in mon_data.get("levels", {}).items():
                    lvl_desc = layer_names.get(str(lvl_num), f"Lvl{lvl_num}")
                    for item in lvl_items:
                        active_layers.append(f"{lvl_desc}:{item.get('namespace', '?')}[pid:{item.get('pid', '?')}]")
                print(f"  • {mon} : {' | '.join(active_layers) if active_layers else 'Aucune'}")
    except Exception:
        pass


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Aurora Wallpaper Engine & Maintenance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Afficher l'état du moteur aurora-wallpaper et couches Wayland")
    subparsers.add_parser("mask", help="Régénérer le masque Blackwall vectoriel haute fidélité")
    subparsers.add_parser("check-links", help="Vérifier la stricte intégrité des hard links dotfiles")
    subparsers.add_parser("restart", help="Redémarrer proprement aurora-wallpaper")

    p_ens = subparsers.add_parser("ensure", help="Garantir la présence de aurora-wallpaper")
    p_ens.add_argument("screen", nargs="?", help="Optionnel pour compatibilité")

    subparsers.add_parser("daemon", help="Lancer le démon d'écoute hotplug IPC pour restauration automatique")

    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "daemon":
        run_wallpaper_daemon()
    elif args.command == "mask":
        generate_blackwall_mask()
        generate_eye_shine_mask()
    elif args.command == "check-links":
        if not audit_hardlinks():
            sys.exit(1)
    elif args.command == "ensure":
        ensure_wallpapers(target_screen=args.screen)
    elif args.command == "restart":
        restart_wallpapers()


if __name__ == "__main__":
    main()
