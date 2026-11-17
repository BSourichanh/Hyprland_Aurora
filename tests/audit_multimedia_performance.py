#!/usr/bin/env python3
"""
Test Suite: Multimedia Ecosystem Performance & Utility Scripts Audit
Target: Waybar GPU, Spotify MPRIS/IPC, screenshot.sh, hyprbar, wofi scripts.
Author: Tester (Zygos Team)
Project: Hyperland / Aurora Ecosystem
Rules: Strict proof-based verification, >= 3 passes per performance measurement.
"""

from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import List

PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
DOTFILES = PROJECT_ROOT / "dotfiles"
WAYBAR_SCRIPTS = DOTFILES / "waybar" / "scripts"
HYPR_SCRIPTS = DOTFILES / "hypr" / "scripts"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(WAYBAR_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WAYBAR_SCRIPTS))


@dataclass
class MetricStats:
    name: str
    passes: List[float]
    unit: str = "ms"

    @property
    def min_val(self) -> float:
        return min(self.passes)

    @property
    def max_val(self) -> float:
        return max(self.passes)

    @property
    def avg_val(self) -> float:
        return sum(self.passes) / len(self.passes)

    def __str__(self) -> str:
        passes_str = ", ".join(f"{p:.3f}" for p in self.passes)
        return (
            f"{self.name:<38} : avg={self.avg_val:.3f}{self.unit} "
            f"(min={self.min_val:.3f}, max={self.max_val:.3f}) [{passes_str}]"
        )


def log_header(title: str):
    print(f"\n{'='*70}\n[AUDIT] {title}\n{'='*70}")


def log_sub(title: str):
    print(f"\n--- {title} ---")


def check(name: str, passed: bool, detail: str = "") -> bool:
    icon = "[PASS]" if passed else "[FAIL]"
    print(f"  {icon} {name:<45} : {detail}")
    return passed


def audit_gpu_module() -> bool:
    log_header("Waybar Module: gpu.py Profiling & Architecture Audit")
    all_ok = True

    import gpu

    # 1.1 Hardware detection & sysfs vs nvidia-smi
    log_sub("Hardware & Driver Detection")
    nvidia_smi = shutil.which("nvidia-smi")
    if not check("nvidia-smi absence", nvidia_smi is None, f"nvidia-smi path: {nvidia_smi}"):
        all_ok = False

    freq_path = gpu.get_gpu_freq_path()
    freq_exists = bool(freq_path and os.path.exists(freq_path))
    if not check("Intel DRM sysfs freq path", freq_exists, f"Path: {freq_path}"):
        all_ok = False

    # 1.2 Performance of sysfs freq read (3 passes)
    log_sub("Performance: get_gpu_freq() (sysfs)")
    passes_freq = []
    freq_val = "N/A"
    for _ in range(3):
        t0 = time.perf_counter()
        freq_val = gpu.get_gpu_freq()
        t1 = time.perf_counter()
        passes_freq.append((t1 - t0) * 1000.0)
    stats_freq = MetricStats("get_gpu_freq()", passes_freq)
    print(f"  {stats_freq}")
    if not check("get_gpu_freq() latency < 1.0ms", stats_freq.avg_val < 1.0, f"Value: {freq_val} MHz"):
        all_ok = False

    # 1.3 Performance of sample_drm_clients() (3 passes)
    log_sub("Performance: sample_drm_clients() (/proc fdinfo)")
    passes_drm = []
    client_counts = []
    for _ in range(3):
        t0 = time.perf_counter()
        _, clients = gpu.sample_drm_clients()
        t1 = time.perf_counter()
        passes_drm.append((t1 - t0) * 1000.0)
        client_counts.append(len(clients))
    stats_drm = MetricStats("sample_drm_clients()", passes_drm)
    print(f"  {stats_drm}")
    if not check("sample_drm_clients() completes", len(client_counts) == 3, f"Clients found: {client_counts[0]}"):
        all_ok = False

    # 1.4 gpu.py --once execution latency (3 passes)
    log_sub("Performance: gpu.py --once Latency")
    passes_once = []
    res = None
    for _ in range(3):
        t0 = time.perf_counter()
        res = subprocess.run(
            [sys.executable, str(WAYBAR_SCRIPTS / "gpu.py"), "--once"],
            capture_output=True,
            text=True,
            check=False,
        )
        t1 = time.perf_counter()
        passes_once.append((t1 - t0) * 1000.0)
    stats_once = MetricStats("gpu.py --once", passes_once)
    print(f"  {stats_once}")
    out_snippet = res.stdout.strip()[:60] if res else ""
    if not check("gpu.py --once exit 0", res is not None and res.returncode == 0, f"Output: {out_snippet}..."):
        all_ok = False

    # 1.5 config.jsonc configuration audit
    log_sub("Config.jsonc Configuration")
    conf_path = DOTFILES / "waybar" / "config.jsonc"
    conf_raw = conf_path.read_text(encoding="utf-8")
    has_gpu = '"custom/gpu"' in conf_raw
    if not check("custom/gpu declared in config.jsonc", has_gpu):
        all_ok = False
    m_int = re.search(r'"restart-interval"\s*:\s*(\d+)', conf_raw)
    restart_int = int(m_int.group(1)) if m_int else None
    if not check("restart-interval set", restart_int == 3, f"Value: {restart_int}s"):
        all_ok = False

    return all_ok


def audit_spotify_ecosystem() -> bool:
    log_header("Spotify Ecosystem: MPRIS, IPC & Memory Audit")
    all_ok = True

    import spotify
    import spotify_ipc

    # 2.1 MPRIS Client Fail-Safe (Spotify Absent)
    log_sub("MPRIS Client Fail-Safe (Spotify Absent)")
    client = spotify.SpotifyMPRISClient()

    passes_status = []
    st_val = ""
    for _ in range(3):
        t0 = time.perf_counter()
        st_val = client.get_playback_status(fresh=True)
        t1 = time.perf_counter()
        passes_status.append((t1 - t0) * 1000.0)
    stats_status = MetricStats("get_playback_status() (absent)", passes_status)
    print(f"  {stats_status}")
    if not check("PlaybackStatus returns empty without throw", st_val == "", f"Returned: '{st_val}'"):
        all_ok = False

    passes_prog = []
    prog_val = None
    for _ in range(3):
        t0 = time.perf_counter()
        prog_val = client.get_progress_data()
        t1 = time.perf_counter()
        passes_prog.append((t1 - t0) * 1000.0)
    stats_prog = MetricStats("get_progress_data() (absent)", passes_prog)
    print(f"  {stats_prog}")
    if not check("Progress returns None gracefully", prog_val is None, f"Returned: {prog_val}"):
        all_ok = False

    # 2.2 UNIX Socket latency & resolution ($AURORA_RUNTIME_DIR / /tmp)
    log_sub("UNIX Domain Socket: spotify_card.sock")
    runtime_base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    runtime_sock = Path(runtime_base) / "aurora" / "spotify_card.sock"
    legacy_sock = Path("/tmp/spotify_card.sock")
    sock_path = runtime_sock if runtime_sock.exists() else legacy_sock
    sock_exists = sock_path.exists()
    check("Socket file presence", sock_exists, str(sock_path))

    if sock_exists:
        passes_sock = []
        resp = b""
        for _ in range(3):
            t0 = time.perf_counter()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(str(sock_path))
                s.sendall(b"status\n")
                resp = s.recv(1024)
            t1 = time.perf_counter()
            passes_sock.append((t1 - t0) * 1000.0)
        stats_sock = MetricStats("Socket round-trip ('status')", passes_sock)
        print(f"  {stats_sock}")
        if not check("Socket responds 'OK'", resp == b"OK\n", f"Response: {resp!r}"):
            all_ok = False

    # 2.3 Mutex Lock ($AURORA_RUNTIME_DIR / /tmp)
    log_sub("Singleton Lock: spotify_card.lock")
    runtime_lock = Path(runtime_base) / "aurora" / "spotify_card.lock"
    legacy_lock = Path("/tmp/spotify_card.lock")
    lock_path = runtime_lock if runtime_lock.exists() else legacy_lock
    lock_exists = runtime_lock.exists() or legacy_lock.exists()
    check("Lock file presence", lock_exists, str(lock_path))

    is_locked = False
    for lp in (runtime_lock, legacy_lock):
        if lp.exists():
            try:
                with open(lp, "r") as lf:
                    try:
                        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(lf, fcntl.LOCK_UN)
                    except (IOError, BlockingIOError):
                        is_locked = True
                        break
            except Exception:
                pass
    if not check("Daemon holds flock mutex", is_locked, f"Locked: {is_locked}"):
        all_ok = False

    # 2.4 Hyprland IPC Service cursorpos Latency
    log_sub("Compositor IPC: Hyprland get_cursor_position()")
    hypr_ipc = spotify_ipc.HyprlandIPCService()
    passes_cursor = []
    cpos = (None, None)
    for _ in range(3):
        t0 = time.perf_counter()
        cpos = hypr_ipc.get_cursor_position()
        t1 = time.perf_counter()
        passes_cursor.append((t1 - t0) * 1000.0)
    stats_cursor = MetricStats("get_cursor_position()", passes_cursor)
    print(f"  {stats_cursor}")
    if not check("Cursor coordinates returned", cpos[0] is not None, f"Position: {cpos}"):
        all_ok = False

    return all_ok


def audit_utility_scripts() -> bool:
    log_header("Utility Scripts: screenshot.sh, hyprbar, wofi-toggle, power-menu")
    all_ok = True

    # 3.1 screenshot.sh
    log_sub("screenshot.sh Audit")
    sc_path = HYPR_SCRIPTS / "screenshot.sh"
    if not check("screenshot.sh exists and executable", os.access(sc_path, os.X_OK)):
        all_ok = False

    sc_src = sc_path.read_text(encoding="utf-8")
    deps = {
        "grim": shutil.which("grim"),
        "slurp": shutil.which("slurp"),
        "wl-copy": shutil.which("wl-copy"),
        "hyprpicker": shutil.which("hyprpicker"),
        "jq": shutil.which("jq"),
        "swappy": shutil.which("swappy"),
    }
    for dep_name, path in deps.items():
        if dep_name == "swappy":
            detail = f"Path: {path}" if path else "Optional (absent on test host)"
            check(f"Dependency: {dep_name}", True, detail)
        else:
            ok = path is not None
            if not check(f"Dependency: {dep_name}", ok, f"Path: {path}"):
                all_ok = False

    if not check("hyprpicker freeze trap present", "trap" in sc_src and "PICKER_PID" in sc_src):
        all_ok = False
    if not check("Multi-monitor focus detection", "FOCUSED_MONITOR" in sc_src and "grim -o" in sc_src):
        all_ok = False

    # 3.2 scripts/hyprbar
    log_sub("scripts/hyprbar Audit")
    bar_path = SCRIPTS_DIR / "hyprbar"
    if not check("hyprbar exists and executable", os.access(bar_path, os.X_OK)):
        all_ok = False

    bar_src = bar_path.read_text(encoding="utf-8")
    has_sigkill = "pkill -9" in bar_src
    sigkill_detail = "Clean signal hygiene (TERM with proper fallback)" if not has_sigkill else "WARNING: Brutal 'pkill -9' found!"
    if not check("Signal hygiene: pkill -9 detection", not has_sigkill, sigkill_detail):
        all_ok = False

    has_sleep_race = "sleep 0.3" in bar_src
    sleep_detail = "Dynamic restart timing (no fixed sleep 0.3)" if not has_sleep_race else "WARNING: Fixed 'sleep 0.3' found!"
    if not check("Restart race condition check", not has_sleep_race, sleep_detail):
        all_ok = False

    # 3.3 wofi-toggle.sh & power-menu.sh
    log_sub("wofi-toggle.sh & power-menu.sh Audit")
    wofi_toggle = HYPR_SCRIPTS / "wofi-toggle.sh"
    power_menu = HYPR_SCRIPTS / "power-menu.sh"

    if not check("wofi-toggle.sh exists and executable", os.access(wofi_toggle, os.X_OK)):
        all_ok = False
    if not check("power-menu.sh exists and executable", os.access(power_menu, os.X_OK)):
        all_ok = False

    wt_src = wofi_toggle.read_text(encoding="utf-8")
    uses_slurp_overlay = "slurp -b '#00000000'" in wt_src and "wait -n" in wt_src
    if not check("wofi-toggle: non-polling slurp overlay", uses_slurp_overlay, "Zero CPU active wait"):
        all_ok = False

    pm_src = power_menu.read_text(encoding="utf-8")
    if not check("power-menu: centered placement", "--location center" in pm_src):
        all_ok = False

    lock_dest = Path.home() / ".config" / "hypr" / "lock.sh"
    if not check("power-menu: lock.sh resolution", lock_dest.exists(), str(lock_dest)):
        all_ok = False

    return all_ok


def main() -> int:
    print("=" * 70)
    print("ZYGOS TEST SUITE: Waybar, GPU & Multimedia Utility Performance Audit")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    ok_gpu = audit_gpu_module()
    ok_spotify = audit_spotify_ecosystem()
    ok_utils = audit_utility_scripts()

    print("\n" + "=" * 70)
    print("AUDIT SUMMARY:")
    print(f"  • Waybar GPU Audit        : {'PASSED' if ok_gpu else 'FAILED'}")
    print(f"  • Spotify Ecosystem Audit : {'PASSED' if ok_spotify else 'FAILED'}")
    print(f"  • Utility Scripts Audit   : {'PASSED' if ok_utils else 'FAILED'}")
    print("=" * 70)

    all_passed = ok_gpu and ok_spotify and ok_utils
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
