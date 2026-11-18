#!/usr/bin/env python3
"""Benchmark reproductible (lecture seule, >= 3 passages) des optimisations OPT-1..OPT-9."""

import concurrent.futures, contextlib, fcntl, glob, importlib.util, json, os, socket, sys, time
from pathlib import Path
from typing import Any, Dict, List, Tuple

PASSES = 3
PROJECT_ROOT = Path(os.environ.get("AURORA_PROJECT_DIR", Path(__file__).resolve().parent.parent))
for _p in (str(PROJECT_ROOT / "scripts"), str(PROJECT_ROOT / "dotfiles" / "hypr" / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import aurora_mcp_server as mcp_srv  # noqa: E402
import aurora_runtime, hypr_ipc, wallpaper_tool  # noqa: E402
from aurora_mcp import media_tools, system_tools  # noqa: E402

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "aurora"


def _require(cond: bool, msg: str) -> None:
    if not cond: raise RuntimeError(msg)

def _fmt_vals(vals: List[float], unit: str = "ms") -> Tuple[str, float]:
    avg = sum(vals) / len(vals)
    return f"[{', '.join(f'{v:.2f}' for v in vals)}] {unit} | moy={avg:.2f} {unit}", avg

def _fmt_gain(old_avg: float, new_avg: float, unit: str = "ms") -> str:
    pct = ((new_avg - old_avg) / old_avg * 100.0) if old_avg > 0 else 0.0
    return f"{new_avg - old_avg:+.2f} {unit} ({pct:+.1f}%, x{(old_avg / new_avg) if new_avg > 0 else 0.0:.1f})"

def _print_pair(lbl_old: str, old_t: List[float], lbl_new: str, new_t: List[float]) -> None:
    s_old, m_old = _fmt_vals(old_t)
    s_new, m_new = _fmt_vals(new_t)
    print(f"  • {lbl_old:<32} : {s_old}\n  • {lbl_new:<32} : {s_new}\n  • {'Gain':<32} : {_fmt_gain(m_old, m_new)}")

def _sock_cmd(cmd_sock: str, cmd: str, timeout: float = 1.0) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(cmd_sock)
        s.sendall(cmd.encode("utf-8"))
        chunks = []
        while (data := s.recv(4096)): chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace")

def _sock_json(cmd_sock: str, query: str) -> Any:
    return json.loads(_sock_cmd(cmd_sock, query, timeout=1.0))

def _fast_is_locked(rt_dir: Path) -> bool:
    for flag, inst in ((rt_dir / "hypr_locked", rt_dir / "hypr_lock_instance.lock"), (Path("/tmp/hypr_locked"), Path("/tmp/hypr_lock_instance.lock"))):
        if not os.path.exists(flag): continue
        try: fd = os.open(str(inst), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        except OSError: return flag.parent == Path("/tmp")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except OSError: return True
        finally: os.close(fd)
    return False


def _sample_drm_fdinfo() -> Tuple[float, Dict[str, Tuple[str, str, int, int]]]:
    clients: Dict[str, Tuple[str, str, int, int]] = {}
    mult = {"B": 1 / 1024.0, "KiB": 1.0, "MiB": 1024.0, "GiB": 1048576.0}
    for pid in os.listdir("/proc"):
        if not pid.isdigit(): continue
        with contextlib.suppress(OSError, ValueError):
            comm = Path(f"/proc/{pid}/comm").read_text("utf-8", "ignore").strip()
            for fd in os.listdir(f"/proc/{pid}/fd"):
                if not any(k in os.readlink(f"/proc/{pid}/fd/{fd}") for k in ("renderD", "card")): continue
                cid, r_ns, mem_kib = "", 0, 0
                for ln in Path(f"/proc/{pid}/fdinfo/{fd}").read_text("utf-8", "ignore").splitlines():
                    if ln.startswith("drm-client-id:"): cid = ln.split(":", 1)[1].strip()
                    elif ln.startswith("drm-engine-render:"): r_ns = int(ln.split(":", 1)[1].split()[0])
                    elif ln.startswith("drm-resident-system0:"):
                        p = ln.split(":", 1)[1].split()
                        mem_kib = int(int(p[0]) * mult.get(p[1] if len(p) > 1 else "KiB", 1.0)) if p else 0
                if cid and cid not in clients: clients[cid] = (pid, comm, r_ns, mem_kib)
    return time.monotonic(), clients

def bench_1_drm_and_binary() -> None:
    print("\n[1/5] Télémétrie DRM GPU live (/proc/*/fdinfo/*) & taille binaire aurora-wallpaper\n      Comptage : delta drm-engine-render (ns) / (dt * 1e9) * 100 sur fenêtre 0.5s, dédupliqué par drm-client-id.")
    per_client: Dict[str, List[float]] = {}
    totals, mem_map = [], {}
    for p in range(PASSES):
        t0, c0 = _sample_drm_fdinfo(); time.sleep(0.5); t1, c1 = _sample_drm_fdinfo()
        dt, pass_tot = max(0.05, t1 - t0), 0.0
        _require(len(c1) > 0, "Aucun client DRM détecté dans /proc/*/fdinfo/*")
        for cid, (pid, comm, r1, mem_kib) in c1.items():
            pct = max(0.0, (r1 - (c0[cid][2] if cid in c0 else r1)) / (dt * 1e9) * 100.0)
            pass_tot += pct
            key = f"{comm}(pid={pid},cid={cid})"
            vals = per_client.setdefault(key, [0.0] * p)
            vals.extend([0.0] * (p - len(vals)) + [pct])
            mem_map[key] = mem_kib / 1024.0
        totals.append(pass_tot)
    for k, vals in sorted(per_client.items(), key=lambda kv: sum(kv[1]), reverse=True):
        if sum(vals) >= 0.05 or "aurora-wallpape" in k: print(f"  • {k:<32} : {_fmt_vals(vals, '%')[0]} | VRAM={mem_map.get(k, 0.0):.1f} MiB")
    freq = next((Path(f).read_text("utf-8").strip() for f in sorted(glob.glob("/sys/class/drm/card*/gt_act_freq_mhz")) if os.path.exists(f)), "N/A")
    print(f"  • {'Total Render Engine DRM':<32} : {_fmt_vals(totals, '%')[0]} | Clients={len(per_client)} | Freq={freq} MHz")
    src_bin, dep_bin = PROJECT_ROOT / "src" / "aurora_wallpaper" / "aurora-wallpaper", Path.home() / ".local" / "bin" / "aurora-wallpaper"
    _require(src_bin.is_file() and dep_bin.is_file(), f"Binaires compilé ou déployé introuvables ({src_bin}, {dep_bin})")
    src_sz, dep_sz = src_bin.stat().st_size, dep_bin.stat().st_size
    _require(src_sz == dep_sz and src_sz <= 112640, f"Binaire non identique ou > 110 Ko ({src_sz}o vs {dep_sz}o)")
    _require(src_bin.read_bytes() == dep_bin.read_bytes(), "Contenu binaire compilé != déployé")
    swaybg_pids = [p for p in os.listdir("/proc") if p.isdigit() and Path(f"/proc/{p}/comm").read_text("utf-8", "ignore").strip() == "swaybg"]
    _require(len(swaybg_pids) == 0, f"Processus swaybg résiduels détectés: {swaybg_pids}")
    print(f"  • {'Binaire déployé (<= 110 Ko)':<32} : {dep_sz} o ({dep_sz/1024:.1f} KiB) == compilé ({src_sz} o) [PASS]\n  • {'Processus swaybg résiduels':<32} : 0 (layer 0 libéré) [PASS]")


def bench_2_wallpaper_watchdog(cmd_sock: str) -> None:
    print("\n[2/5] Latence Watchdog IPC Wallpaper (3 forks CLI vs socket UNIX direct + stat() lock)\n      Comptage : durée totale (ms) pour obtenir layers + monitors + état verrouillage.")
    old_t, new_t = [], []
    for _ in range(PASSES):
        t0 = time.perf_counter()
        layers_old, mons_old = wallpaper_tool.get_active_layer_wallpaper_screens(), wallpaper_tool.get_hyprland_connected_screens()
        lock_old = bool(aurora_runtime.get_lock_state(clean_orphans=False)["locked"])
        old_t.append((time.perf_counter() - t0) * 1000.0)
        _require(len(mons_old) > 0, "Échec get_hyprland_connected_screens()")
        t0 = time.perf_counter()
        l_raw, m_raw = _sock_json(cmd_sock, "j/layers"), _sock_json(cmd_sock, "j/monitors")
        layers_new = {mon: it.get("pid") for mon, md in l_raw.items() for items in md.get("levels", {}).values() for it in items if it.get("namespace") == "aurora-wallpaper"}
        mons_new = [m["name"] for m in m_raw if m.get("name") and not m.get("disabled", False)]
        lock_new = _fast_is_locked(RUNTIME_DIR)
        new_t.append((time.perf_counter() - t0) * 1000.0)
        _require(set(mons_new) == set(mons_old) and set(layers_new) == set(layers_old) and lock_new == lock_old, "Divergence watchdog IPC")
    _require(all(t < 5.0 for t in new_t), f"Requête socket directe IPC trop lente (>= 5 ms sur {PASSES} passages): {new_t}")
    _print_pair("Actuel (3 forks hyprctl+pgrep)", old_t, "Optimisé (socket UNIX + stat)", new_t)


def bench_3_hypr_ipc(cmd_sock: str) -> None:
    iters = 50
    print(f"\n[3/5] Latence hypr_ipc (is_session_locked + get_cursor_position x {iters} itérations / passage)\n      Comptage : temps cumulé (ms) de {iters} appels is_session_locked() + cursorpos.")
    old_t, new_t = [], []
    for _ in range(PASSES):
        t0 = time.perf_counter()
        for _ in range(iters):
            _ = hypr_ipc.is_session_locked()
            _require(hypr_ipc.get_cursor_position()[0] is not None, "get_cursor_position() a retourné None")
        old_t.append((time.perf_counter() - t0) * 1000.0)
        t0 = time.perf_counter()
        for _ in range(iters):
            _ = _fast_is_locked(RUNTIME_DIR)
            x_s, y_s = _sock_cmd(cmd_sock, "cursorpos", timeout=0.04).strip().split(",", 1)
            _ = (int(x_s), int(y_s))
        new_t.append((time.perf_counter() - t0) * 1000.0)
    _require(all(t < 10.0 for t in new_t), f"Cache hypr_ipc optimisé >= 10 ms pour {iters} req: {new_t}")
    _require(all(t < 10.0 for t in old_t), f"hypr_ipc actuel >= 10 ms pour {iters} req: {old_t}")
    _print_pair("Actuel (makedirs/chmod/listdir)", old_t, "Optimisé (socket + runtime cache)", new_t)


def bench_4_compact_workspaces() -> None:
    print("\n[4/5] Latence compact_workspaces (appel MCP actuel vs in-process avec cache j/workspacerules)\n      Comptage : durée totale (ms) d'un appel compact_workspaces (lecture seule, hypr_batch neutralisé).")
    spec = importlib.util.spec_from_file_location("wac_bench", str(PROJECT_ROOT / "dotfiles" / "hypr" / "scripts" / "workspace-autocompact.py"))
    _require(spec is not None and spec.loader is not None, "Impossible de charger workspace-autocompact.py")
    wac = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wac)  # type: ignore[union-attr]
    old_t, new_t, queries = [], [], []
    for _ in range(PASSES):
        t0 = time.perf_counter()
        res = system_tools.compact_workspaces()
        old_t.append((time.perf_counter() - t0) * 1000.0)
        _require(bool(res.get("ok")), f"system_tools.compact_workspaces() échoué: {res}")
    cached_cfg, orig_cfg, orig_batch, orig_json, orig_lock = wac.get_monitor_configs(), wac.get_monitor_configs, wac.hypr_batch, wac.hypr_json, wac.is_session_locked
    wac.get_monitor_configs, wac.hypr_batch, wac.is_session_locked = (lambda: cached_cfg), (lambda _d: ""), (lambda: (orig_lock(), False)[1])
    wac.hypr_json = lambda q, timeout=1.0: (queries.append(q), orig_json(q, timeout=timeout))[1]
    try:
        for _ in range(PASSES):
            queries.clear()
            t0 = time.perf_counter()
            _ = wac.compact_workspaces()
            new_t.append((time.perf_counter() - t0) * 1000.0)
            _require(queries == ["j/monitors", "j/clients", "j/workspaces"], f"Requêtes inattendues: {queries}")
    finally:
        wac.get_monitor_configs, wac.hypr_batch, wac.hypr_json, wac.is_session_locked = orig_cfg, orig_batch, orig_json, orig_lock
    _require(all(t < 10.0 for t in new_t), f"compact_workspaces in-process >= 10 ms: {new_t}")
    _require(all(t < 10.0 for t in old_t), f"compact_workspaces MCP >= 10 ms: {old_t}")
    _print_pair("Actuel (MCP sans --once, bloqué)", old_t, "Optimisé (in-proc + cache rules)", new_t)


def _unified_proc_scan() -> Tuple[List[Tuple[int, float]], List[int], List[int]]:
    wp, wb, hl = [], [], []
    for entry in os.listdir("/proc"):
        if not entry.isdigit(): continue
        with contextlib.suppress(OSError):
            comm = Path(f"/proc/{entry}/comm").read_text("utf-8", "ignore").strip()
            if comm in ("aurora-wallpape", "aurora-wallpaper"):
                rss = next((int(ln.split()[1]) / 1024.0 for ln in Path(f"/proc/{entry}/status").read_text("utf-8", "ignore").splitlines() if ln.startswith("VmRSS:")), 0.0)
                wp.append((int(entry), round(rss, 1)))
            elif comm == "waybar": wb.append(int(entry))
            elif comm == "hyprlock": hl.append(int(entry))
    return wp, wb, hl


def bench_5_mcp_status(cmd_sock: str) -> None:
    print("\n[5/5] Latence aurora_mcp_server.get_aurora_status() (actuel vs socket UNIX + /proc unifié)\n      Comptage : durée totale (ms) diagnostic complet actuel vs collecte socket+proc (et variante complète parallèle).")
    old_t, core_t, full_t = [], [], []
    for _ in range(PASSES):
        t0 = time.perf_counter()
        st = mcp_srv.get_aurora_status()
        old_t.append((time.perf_counter() - t0) * 1000.0)
        _require("wallpaper_engine" in st and "monitors" in st, "get_aurora_status() invalide")
        t0 = time.perf_counter()
        _ = (_sock_json(cmd_sock, "j/layers"), _sock_json(cmd_sock, "j/monitors"), _sock_json(cmd_sock, "j/workspaces"))
        wp, wb, _ = _unified_proc_scan()
        core_t.append((time.perf_counter() - t0) * 1000.0)
        _require(len(wb) == len(st["waybar"]["pids"]) and len(wp) == st["wallpaper_engine"]["process_count"], "Divergence /proc")
        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(fn) for fn in (media_tools._get_swaync_info, media_tools._get_audio_info, media_tools._get_spotify_info, system_tools._check_hardlinks_dict)]
            _ = (_sock_json(cmd_sock, "j/layers"), _sock_json(cmd_sock, "j/monitors"), _sock_json(cmd_sock, "j/workspaces"))
            _ = (_unified_proc_scan(), system_tools._get_gpu_info(), _fast_is_locked(RUNTIME_DIR))
            for fut in futs: fut.result()
        full_t.append((time.perf_counter() - t0) * 1000.0)
    _require(all(t < 45.0 for t in old_t), f"get_aurora_status() actuel >= 45 ms: {old_t}")
    _require(all(t < 45.0 for t in full_t), f"get_aurora_status() complet optimisé >= 45 ms: {full_t}")
    s_old, m_old = _fmt_vals(old_t)
    s_core, m_core = _fmt_vals(core_t)
    s_full, m_full = _fmt_vals(full_t)
    print(f"  • {'Actuel get_aurora_status()':<32} : {s_old}\n  • {'Socket UNIX + /proc unifié':<32} : {s_core} | Gain: {_fmt_gain(m_old, m_core)}\n  • {'Complet optimisé (+ parallèle)':<32} : {s_full} | Gain: {_fmt_gain(m_old, m_full)}")


def main() -> int:
    print(f"{'=' * 72}\nBENCHMARK OPTIMISATIONS AURORA / HYPRLAND (3 PASSAGES, LECTURE SEULE)\nRacine projet : {PROJECT_ROOT}\n{'=' * 72}")
    cmd_sock, _ = hypr_ipc.get_hypr_sockets()
    _require(bool(cmd_sock and os.path.exists(cmd_sock)), "Socket Hyprland (.socket.sock) introuvable")
    for fn in (bench_1_drm_and_binary, lambda: bench_2_wallpaper_watchdog(cmd_sock), lambda: bench_3_hypr_ipc(cmd_sock), bench_4_compact_workspaces, lambda: bench_5_mcp_status(cmd_sock)):  # type: ignore[arg-type]
        fn()
    print(f"\n{'=' * 72}\nRESULT: PASS — Tous les benchmarks (>= 3 passages) ont réussi.\n{'=' * 72}")
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as exc:
        print(f"RESULT: FAIL — {exc}", file=sys.stderr)
        sys.exit(1)
