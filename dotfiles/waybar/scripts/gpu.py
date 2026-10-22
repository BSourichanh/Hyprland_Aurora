#!/usr/bin/env python3
"""
GPU Monitoring Module for Waybar (Aurora Theme)
-----------------------------------------------
Mesure en temps réel l'utilisation du GPU Intel (i915 / UHD 630) sans dépendance
externe, via l'API DRM kernel (/proc/*/fdinfo/*) et sysfs (/sys/class/drm/card*).
"""

import os
import sys
import time
import json
import signal
import fcntl

INTERVAL = 3.0
LOCK_FILE = "/dev/shm/waybar_gpu.lock"
CACHE_FILE = "/dev/shm/waybar_gpu_cache.json"


def write_cache(payload: dict) -> None:
    """Écrit le payload Waybar dans la mémoire partagée (/dev/shm) de manière atomique."""
    tmp_path = f"{CACHE_FILE}.tmp"
    try:
        data = {"ts": time.time(), "payload": payload}
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, CACHE_FILE)
    except Exception:
        pass


def read_cache(max_age: float = 6.0):
    """Lit le payload depuis la mémoire partagée si encore valide."""
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) <= max_age:
            return data.get("payload")
    except Exception:
        pass
    return None

SYSFS_FREQ_PATHS = [
    "/sys/class/drm/card1/gt_act_freq_mhz",
    "/sys/class/drm/card0/gt_act_freq_mhz",
    "/sys/class/drm/card1/gt/gt0/rps_act_freq_mhz",
    "/sys/class/drm/card0/gt/gt0/rps_act_freq_mhz",
]


def get_gpu_freq_path() -> str:
    for path in SYSFS_FREQ_PATHS:
        if os.path.exists(path):
            return path
    return ""


FREQ_PATH = get_gpu_freq_path()


def sample_drm_clients():
    """Échantillonne les statistiques de calcul DRM (Fast-Path via readlink sur /proc/*/fd/*)."""
    now = time.time()
    clients = {}

    try:
        proc_entries = os.listdir("/proc")
    except Exception:
        return now, clients

    for pid in proc_entries:
        if not pid.isdigit():
            continue
        fd_dir = f"/proc/{pid}/fd"
        try:
            for fd in os.listdir(fd_dir):
                try:
                    target = os.readlink(f"{fd_dir}/{fd}")
                    if "renderD" not in target and "card" not in target:
                        continue
                    path = f"/proc/{pid}/fdinfo/{fd}"
                    with open(path, "r") as f:
                        cid = None
                        r_ns = 0
                        v_ns = 0
                        mem_kib = 0
                        for line in f:
                            if line.startswith("drm-client-id:"):
                                cid = line.split(":")[-1].strip()
                            elif line.startswith("drm-engine-render:"):
                                parts = line.split(":")[-1].strip().split()
                                if parts:
                                    r_ns = int(parts[0])
                            elif line.startswith("drm-engine-video:"):
                                parts = line.split(":")[-1].strip().split()
                                if parts:
                                    v_ns = int(parts[0])
                            elif line.startswith("drm-resident-system0:"):
                                parts = line.split(":")[-1].strip().split()
                                if parts:
                                    mem_kib = int(parts[0])
                        if cid and cid not in clients:
                            clients[cid] = {"render": r_ns, "video": v_ns, "mem": mem_kib}
                except (OSError, IOError, ValueError):
                    pass
        except (OSError, IOError):
            pass

    return now, clients


def get_gpu_freq() -> str:
    if FREQ_PATH:
        try:
            with open(FREQ_PATH, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    return "N/A"


def calculate_metrics(t0, c0, t1, c1):
    """Calcule les pourcentages d'utilisation du GPU entre deux échantillons."""
    dt = max(0.001, t1 - t0)
    d_render = 0
    d_video = 0
    total_mem_kib = 0

    for cid, data in c1.items():
        total_mem_kib += data.get("mem", 0)
        if cid in c0:
            d_r = data["render"] - c0[cid]["render"]
            d_v = data["video"] - c0[cid]["video"]
            if d_r > 0:
                d_render += d_r
            if d_v > 0:
                d_video += d_v

    pct_render = min(100.0, (d_render / (dt * 1e9)) * 100.0)
    pct_video = min(100.0, (d_video / (dt * 1e9)) * 100.0)
    total_pct = min(100, int(round(pct_render + pct_video)))

    return total_pct, pct_render, pct_video, total_mem_kib


def build_waybar_payload(total_pct, pct_render, pct_video, total_mem_kib):
    freq = get_gpu_freq()
    mem_mb = total_mem_kib / 1024.0

    if total_pct >= 95:
        css_class = "critical"
    elif total_pct >= 80:
        css_class = "warning"
    else:
        css_class = "normal"

    icon_span = "<span color=\"#00f0ff\">\U000f08ae</span>&#8194;"
    text = f"{icon_span}{total_pct}%"

    tooltip = (
        f"GPU : Intel UHD Graphics 630\n"
        f"Charge : {total_pct}%\n"
        f"  • Rendu 3D : {pct_render:.1f}%\n"
        f"  • Décodage vidéo : {pct_video:.1f}%\n"
        f"Fréquence : {freq} MHz\n"
        f"VRAM allouée : {mem_mb:.0f} Mo"
    )

    return {
        "text": text,
        "tooltip": tooltip,
        "class": css_class,
        "percentage": total_pct
    }


def main():
    def handle_sig(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    if "--once" in sys.argv:
        cached = read_cache(max_age=INTERVAL)
        if cached:
            print(json.dumps(cached, ensure_ascii=False))
            return
        t_prev, c_prev = sample_drm_clients()
        time.sleep(0.8)
        t_now, c_now = sample_drm_clients()
        total_pct, pct_render, pct_video, total_mem = calculate_metrics(t_prev, c_prev, t_now, c_now)
        payload = build_waybar_payload(total_pct, pct_render, pct_video, total_mem)
        write_cache(payload)
        print(json.dumps(payload, ensure_ascii=False))
        return

    # Gestion singleton Leader-Follower pour multi-écrans (Waybar DP-1 & DP-2)
    lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
    is_leader = False

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        is_leader = True
    except (BlockingIOError, OSError):
        is_leader = False

    t_prev = 0
    c_prev = {}

    if is_leader:
        t_prev, c_prev = sample_drm_clients()
        time.sleep(0.8)
        t_now, c_now = sample_drm_clients()
        total_pct, pct_render, pct_video, total_mem = calculate_metrics(t_prev, c_prev, t_now, c_now)
        payload = build_waybar_payload(total_pct, pct_render, pct_video, total_mem)
        write_cache(payload)
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        t_prev, c_prev = t_now, c_now
    else:
        # Instance Follower : attend l'apparition du premier cache Leader (max 1.5s)
        cached = None
        for _ in range(15):
            cached = read_cache(max_age=INTERVAL + 1.0)
            if cached:
                print(json.dumps(cached, ensure_ascii=False), flush=True)
                break
            time.sleep(0.1)
        if not cached:
            t_prev, c_prev = sample_drm_clients()
            time.sleep(0.5)
            t_now, c_now = sample_drm_clients()
            total_pct, pct_render, pct_video, total_mem = calculate_metrics(t_prev, c_prev, t_now, c_now)
            payload = build_waybar_payload(total_pct, pct_render, pct_video, total_mem)
            print(json.dumps(payload, ensure_ascii=False), flush=True)

    while True:
        try:
            time.sleep(INTERVAL)

            if not is_leader:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    is_leader = True
                    t_prev, c_prev = sample_drm_clients()
                except (BlockingIOError, OSError):
                    pass

            if is_leader:
                t_now, c_now = sample_drm_clients()
                total_pct, pct_render, pct_video, total_mem = calculate_metrics(t_prev, c_prev, t_now, c_now)
                payload = build_waybar_payload(total_pct, pct_render, pct_video, total_mem)
                write_cache(payload)
                print(json.dumps(payload, ensure_ascii=False), flush=True)
                t_prev, c_prev = t_now, c_now
            else:
                cached = read_cache(max_age=INTERVAL * 2)
                if cached:
                    print(json.dumps(cached, ensure_ascii=False), flush=True)
        except (BrokenPipeError, IOError):
            sys.exit(0)
        except Exception:
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
