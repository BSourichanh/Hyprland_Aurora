#!/usr/bin/env python3
"""
GPU Monitoring Module for Waybar (Aurora Theme)
-----------------------------------------------
Mesure en temps réel l'utilisation du GPU Intel (i915 / UHD 630) sans dépendance
externe, via l'API DRM kernel (/proc/*/fdinfo/*) et sysfs (/sys/class/drm/card*).
"""

import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

HYPR_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "hypr" / "scripts"
if str(HYPR_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(HYPR_SCRIPTS_DIR))

from hypr_ipc import get_aurora_runtime_dir

INTERVAL = 3.0
RUNTIME_DIR = get_aurora_runtime_dir()
LOCK_FILE = str(RUNTIME_DIR / "waybar_gpu.lock")
CACHE_FILE = str(RUNTIME_DIR / "waybar_gpu.json")

SYSFS_FREQ_PATHS = [
    "/sys/class/drm/card1/gt_act_freq_mhz",
    "/sys/class/drm/card0/gt_act_freq_mhz",
    "/sys/class/drm/card1/gt/gt0/rps_act_freq_mhz",
    "/sys/class/drm/card0/gt/gt0/rps_act_freq_mhz",
]

_cached_drm_pids = set()
_cached_drm_fds = {}
_last_proc_scan = 0.0
DISCOVERY_INTERVAL = 30.0


def write_cache(payload: dict) -> None:
    """Écrit le payload Waybar dans $AURORA_RUNTIME_DIR de manière atomique (0600)."""
    target = Path(CACHE_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp_gpu_", dir=str(target.parent))
        os.chmod(tmp_name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "payload": payload}, f)
        os.replace(tmp_name, CACHE_FILE)
    except OSError:
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def read_cache(max_age: float = 6.0):
    """Lit le payload depuis $AURORA_RUNTIME_DIR/waybar_gpu.json si encore valide."""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("ts", 0) <= max_age:
            return data.get("payload")
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pass
    return None


def get_gpu_freq_path() -> str:
    for path in SYSFS_FREQ_PATHS:
        if os.path.exists(path):
            return path
    return ""


FREQ_PATH = get_gpu_freq_path()


def _discover_drm_pids():
    """Slow-Path : exploration de /proc pour répertorier les PIDs utilisant le DRM."""
    global _cached_drm_pids, _cached_drm_fds, _last_proc_scan
    new_pids = set()
    new_fds = {}
    try:
        proc_entries = os.listdir("/proc")
    except OSError:
        return
    for pid in proc_entries:
        if not pid.isdigit():
            continue
        fd_dir = f"/proc/{pid}/fd"
        try:
            seen_cids = set()
            for fd in os.listdir(fd_dir):
                try:
                    target = os.readlink(f"{fd_dir}/{fd}")
                    if "renderD" in target or "card" in target:
                        cid = None
                        with open(f"/proc/{pid}/fdinfo/{fd}", "r", encoding="utf-8") as f:
                            for line in f:
                                if line.startswith("drm-client-id:"):
                                    cid = line.split(":", 1)[-1].strip()
                                    break
                        if cid and cid not in seen_cids:
                            seen_cids.add(cid)
                            new_pids.add(pid)
                            new_fds.setdefault(pid, []).append(fd)
                except OSError:
                    pass
        except OSError:
            pass
    _cached_drm_pids = new_pids
    _cached_drm_fds = new_fds
    _last_proc_scan = time.time()


def _parse_mem_kib(parts: list) -> int:
    if not parts:
        return 0
    val = int(parts[0])
    unit = parts[1] if len(parts) > 1 else "KiB"
    if unit == "B":
        return val // 1024
    if unit == "MiB":
        return val * 1024
    if unit == "GiB":
        return val * 1024 * 1024
    return val


def sample_drm_clients(force_discovery: bool = False):
    """Échantillonne les statistiques DRM via bi-cadence (lazy discovery, Fast-Path en cache)."""
    global _last_proc_scan
    now = time.time()

    if force_discovery or not _cached_drm_fds or (now - _last_proc_scan > DISCOVERY_INTERVAL):
        _discover_drm_pids()

    clients = {}
    for pid in list(_cached_drm_fds.keys()):
        if not os.path.exists(f"/proc/{pid}"):
            _cached_drm_fds.pop(pid, None)
            _cached_drm_pids.discard(pid)
            continue

        valid_fds = []
        for fd in list(_cached_drm_fds.get(pid, [])):
            path = f"/proc/{pid}/fdinfo/{fd}"
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                cid, r_ns, v_ns, mem_kib = None, 0, 0, 0
                for line in content.splitlines():
                    if line.startswith("drm-client-id:"):
                        cid = line.split(":", 1)[-1].strip()
                    elif line.startswith("drm-engine-render:"):
                        parts = line.split(":", 1)[-1].strip().split()
                        if parts:
                            r_ns = int(parts[0])
                    elif line.startswith("drm-engine-video:"):
                        parts = line.split(":", 1)[-1].strip().split()
                        if parts:
                            v_ns = int(parts[0])
                    elif line.startswith("drm-resident-system0:"):
                        mem_kib = _parse_mem_kib(line.split(":", 1)[-1].strip().split())
                valid_fds.append(fd)
                if cid and cid not in clients:
                    clients[cid] = {"render": r_ns, "video": v_ns, "mem": mem_kib}
            except (OSError, ValueError):
                continue

        if valid_fds:
            _cached_drm_fds[pid] = valid_fds
        else:
            _cached_drm_fds.pop(pid, None)
            _cached_drm_pids.discard(pid)

    return now, clients


def get_gpu_freq() -> str:
    if FREQ_PATH:
        try:
            with open(FREQ_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
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
    total_pct = min(100, int(round(max(pct_render, pct_video))))

    return total_pct, pct_render, pct_video, total_mem_kib


def build_waybar_payload(total_pct, pct_render, pct_video, total_mem_kib):
    freq = get_gpu_freq()
    mem_mb = total_mem_kib / 1024.0

    css_class = "normal"
    icon_span = '<span color="#00f0ff">\U000f08ae</span>  '
    text = f"{icon_span}{total_pct}%"
    tooltip = (
        f"GPU : Intel UHD Graphics 630\n"
        f"Charge : {total_pct}%\n"
        f"  • Rendu 3D : {pct_render:.1f}%\n"
        f"  • Décodage vidéo : {pct_video:.1f}%\n"
        f"Fréquence : {freq} MHz\n"
        f"VRAM allouée : {mem_mb:.0f} Mo"
    )
    return {"text": text, "tooltip": tooltip, "class": css_class, "percentage": total_pct}


def _emit_payload(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _exit_broken_pipe() -> None:
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)
    except OSError:
        pass
    sys.exit(0)


def _sample_and_publish(t_prev, c_prev):
    t_now, c_now = sample_drm_clients()
    total_pct, pct_render, pct_video, total_mem = calculate_metrics(t_prev, c_prev, t_now, c_now)
    payload = build_waybar_payload(total_pct, pct_render, pct_video, total_mem)
    write_cache(payload)
    _emit_payload(payload)
    return t_now, c_now


def main():
    def handle_sig(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    try:
        if "--once" in sys.argv:
            cached = read_cache(max_age=INTERVAL)
            if cached:
                _emit_payload(cached)
                return
            t_prev, c_prev = sample_drm_clients()
            time.sleep(0.8)
            _sample_and_publish(t_prev, c_prev)
            return

        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        is_leader = False
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            is_leader = True
        except (BlockingIOError, OSError):
            is_leader = False

        t_prev, c_prev = 0.0, {}
        if is_leader:
            t_prev, c_prev = sample_drm_clients()
            time.sleep(0.8)
            t_prev, c_prev = _sample_and_publish(t_prev, c_prev)
        else:
            cached = None
            for _ in range(15):
                cached = read_cache(max_age=INTERVAL + 1.0)
                if cached:
                    _emit_payload(cached)
                    break
                time.sleep(0.1)
            if not cached:
                t_p, c_p = sample_drm_clients()
                time.sleep(0.5)
                t_n, c_n = sample_drm_clients()
                total_pct, pct_r, pct_v, total_mem = calculate_metrics(t_p, c_p, t_n, c_n)
                _emit_payload(build_waybar_payload(total_pct, pct_r, pct_v, total_mem))

        while True:
            try:
                time.sleep(INTERVAL)

                if not is_leader:
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        is_leader = True
                        t_prev, c_prev = sample_drm_clients()
                        cached = read_cache(max_age=INTERVAL * 2)
                        if cached:
                            _emit_payload(cached)
                            continue
                        time.sleep(0.8)
                    except (BlockingIOError, OSError):
                        pass

                if is_leader:
                    t_prev, c_prev = _sample_and_publish(t_prev, c_prev)
                else:
                    cached = read_cache(max_age=INTERVAL * 2)
                    if cached:
                        _emit_payload(cached)
            except (BrokenPipeError, IOError):
                _exit_broken_pipe()
            except Exception:
                time.sleep(INTERVAL)
    except BrokenPipeError:
        _exit_broken_pipe()


if __name__ == "__main__":
    main()