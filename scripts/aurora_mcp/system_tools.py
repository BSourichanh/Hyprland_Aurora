"""
Aurora MCP System Tools Module
Manages Hyprland IPC, DRM/GPU metrics, hardlink audits, session locking, and wallpaper engine.
"""

import contextlib
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from aurora_runtime import (  # noqa: E402
    audit_dotfiles_hardlinks,
    get_aurora_runtime_dir,
    get_lock_state,
    hypr_socket_json,
    spawn_detached,
)

PROJECT_DIR = SCRIPTS_DIR.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
WALLPAPER_TOOL = SCRIPTS_DIR / "wallpaper_tool.py"
HYPRBAR_TOOL = SCRIPTS_DIR / "hyprbar"
LOCK_SCRIPT = DOTFILES_DIR / "hypr" / "lock.sh"
_WAC_MODULE: Optional[Any] = None
_WAC_LOCK = threading.Lock()


def _run_cmd(cmd: List[str], timeout: float = 5.0) -> Dict[str, Any]:
    """Executes subprocess with stdin isolated from MCP stdio and explicit error handling."""
    try:
        res = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": res.returncode == 0,
            "returncode": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": f"Timeout ({timeout}s) sur {' '.join(cmd)}"}
    except (FileNotFoundError, OSError) as exc:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)}


def _run_hyprctl(args: List[str]) -> Any:
    """Executes Hyprland JSON IPC via UNIX socket with hyprctl -j fallback."""
    if not args:
        return None
    return hypr_socket_json("j/" + " ".join(args), timeout=1.5)


def _check_hardlinks_dict() -> Dict[str, Any]:
    """Audits the canonical 42 hard links between dotfiles/ and ~/.config/."""
    return audit_dotfiles_hardlinks(DOTFILES_DIR, CONFIG_DIR)


def _get_gpu_info() -> Dict[str, Any]:
    """Retrieves Intel GPU metrics from $AURORA_RUNTIME_DIR/waybar_gpu.json, /dev/shm fallback, or sysfs."""
    runtime_cache = get_aurora_runtime_dir() / "waybar_gpu.json"
    legacy_cache = Path("/dev/shm/waybar_gpu_cache.json")

    freq = 0
    for card in sorted(glob.glob("/sys/class/drm/card*/gt_act_freq_mhz")):
        with contextlib.suppress(Exception):
            freq = int(Path(card).read_text(encoding="utf-8").strip())
            break

    for cache_file in (runtime_cache, legacy_cache):
        if not cache_file.exists():
            continue
        with contextlib.suppress(Exception):
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - data.get("ts", 0) <= 6.0:
                payload = data.get("payload", {})
                return {
                    "percentage": payload.get("percentage", 0),
                    "frequency_mhz": freq,
                    "tooltip": payload.get("tooltip", ""),
                    "active": True,
                }

    return {
        "percentage": 0,
        "frequency_mhz": freq,
        "tooltip": "",
        "active": False,
    }


def _get_lock_info(hyprlock_running: Optional[bool] = None) -> Dict[str, Any]:
    """Checks session lock state via /proc comm, flock instance, and runtime flag."""
    return get_lock_state(clean_orphans=False, hyprlock_running=hyprlock_running)


def _resolve_pillow_cmd(script_args: List[str]) -> List[str]:
    """Finds a Python command with Pillow available for mask generation."""
    if importlib.util.find_spec("PIL") is not None:
        return [sys.executable, "-B", str(WALLPAPER_TOOL), *script_args]
    sys_py = shutil.which("python3", path="/usr/local/bin:/usr/bin:/bin") or "/usr/bin/python3"
    if Path(sys_py).exists():
        probe = _run_cmd([sys_py, "-B", "-c", "import PIL"], timeout=3.0)
        if probe["ok"]:
            return [sys_py, "-B", str(WALLPAPER_TOOL), *script_args]
    uv_bin = shutil.which("uv")
    if uv_bin:
        return [uv_bin, "run", "--with", "pillow", "python3", "-B", str(WALLPAPER_TOOL), *script_args]
    return [sys.executable, "-B", str(WALLPAPER_TOOL), *script_args]


def manage_wallpaper(action: str, screen: Optional[str] = None) -> Dict[str, Any]:
    """
    Manages Aurora Wallpaper Engine processes and maintenance commands.
    - action: 'status', 'mask', 'check-links', 'restart', 'daemon', 'ensure'
    - screen: optional monitor target (e.g. 'DP-1', 'DP-2') for 'ensure'
    """
    valid_actions = ("status", "mask", "check-links", "restart", "daemon", "ensure")
    if action not in valid_actions:
        return {"ok": False, "error": f"Action inconnue: {action}. Utiliser {', '.join(valid_actions)}."}

    if screen and action != "ensure":
        return {"ok": False, "error": f"Le paramètre 'screen' n'est supporté que pour l'action 'ensure', pas '{action}'."}

    if action == "daemon":
        pid = spawn_detached([sys.executable, "-B", str(WALLPAPER_TOOL), "daemon"], cwd=PROJECT_DIR)
        return {"ok": True, "action": "daemon", "pid": pid, "stdout": "Démon wallpaper lancé", "stderr": ""}

    if action == "mask":
        cmd = _resolve_pillow_cmd(["mask"])
        timeout = 45.0
    elif action == "ensure":
        cmd = [sys.executable, "-B", str(WALLPAPER_TOOL), "ensure"]
        if screen and screen.strip():
            cmd.append(screen.strip())
        timeout = 20.0
    else:
        cmd = [sys.executable, "-B", str(WALLPAPER_TOOL), action]
        timeout = 20.0

    res = _run_cmd(cmd, timeout=timeout)
    return {
        "ok": res["ok"],
        "action": action,
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def manage_hyprbar(action: str) -> Dict[str, Any]:
    """
    Controls Waybar and the Spotify ecosystem via hyprbar CLI.
    - action: 'restart' (full restart), 'reload' (CSS reload), 'toggle' (hide/show), 'status'
    """
    if action not in ("restart", "reload", "toggle", "status"):
        return {"ok": False, "error": f"Action non valide: {action}. Utiliser 'restart', 'reload', 'toggle' ou 'status'."}

    res = _run_cmd([str(HYPRBAR_TOOL), action], timeout=10.0)
    return {
        "ok": res["ok"],
        "action": action,
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def lock_session(action: str = "lock") -> Dict[str, Any]:
    """
    Controls and inspects Hyprland session locking (lock.sh / Hyprlock).
    - action: 'lock' (trigger secure lock asynchronously), 'status' (check lock state)
    """
    if action == "status":
        return {"ok": True, "lock": _get_lock_info()}

    if action == "lock":
        if not LOCK_SCRIPT.exists():
            return {"ok": False, "error": "Script lock.sh introuvable"}
        spawn_detached(["bash", str(LOCK_SCRIPT)])
        time.sleep(0.3)
        return {
            "ok": True,
            "action": "lock",
            "message": "Protocole de verrouillage lock.sh déclenché",
            "lock": _get_lock_info(),
        }

    return {"ok": False, "error": f"Action lock inconnue: {action}. Utiliser 'lock' ou 'status'."}


def reload_all() -> Dict[str, Any]:
    """
    Performs an atomic full reload of the Aurora desktop ecosystem:
    - Hyprland configuration (hyprctl reload)
    - Waybar status bar (hyprbar restart)
    - SwayNC notification daemon (swaync-client -R && -rs)
    - Wallpaper Engine Lucy layer verification (wallpaper_tool.py ensure)
    - Canonical hardlinks integrity audit (42/42 check)
    """
    if _get_lock_info()["locked"]:
        return {
            "ok": False,
            "error": "Session verrouillée (verrou actif). Rechargement ignoré par sécurité.",
            "actions": {},
        }

    results: Dict[str, Any] = {}

    res_hypr = _run_cmd(["hyprctl", "reload"], timeout=5.0)
    results["hyprctl"] = {"ok": res_hypr["ok"], "output": res_hypr["stdout"] or res_hypr["stderr"]}

    res_bar = _run_cmd([str(HYPRBAR_TOOL), "restart"], timeout=10.0)
    results["waybar"] = {"ok": res_bar["ok"], "output": res_bar["stdout"] or res_bar["stderr"]}

    res_swaync_cfg = _run_cmd(["swaync-client", "-R"], timeout=3.0)
    res_swaync_css = _run_cmd(["swaync-client", "-rs"], timeout=3.0)
    results["swaync"] = {"ok": res_swaync_cfg["ok"] and res_swaync_css["ok"]}

    res_wp = _run_cmd([sys.executable, "-B", str(WALLPAPER_TOOL), "ensure"], timeout=10.0)
    results["wallpaper"] = {"ok": res_wp["ok"], "output": res_wp["stdout"] or res_wp["stderr"]}

    results["hardlinks"] = _check_hardlinks_dict()

    return {
        "ok": all(r.get("ok", False) for r in results.values()),
        "actions": results,
    }


def audit_hardlinks() -> Dict[str, Any]:
    """
    Audits the integrity of the 42 canonical hard links between dotfiles/ and ~/.config/.
    Ensures identical inodes (st_nlink >= 2) and zero directory/file symlinks.
    """
    return _check_hardlinks_dict()


def wofi_launch(mode: str = "drun") -> Dict[str, Any]:
    """
    Launches Wofi in 'drun' (applications) or 'power' (power menu) mode.
    Runs detached without polluting MCP stdio or leaving zombies.
    """
    if mode == "power":
        script = DOTFILES_DIR / "hypr" / "scripts" / "power-menu.sh"
        spawn_detached(["bash", str(script)])
        return {"ok": True, "mode": "power", "message": "Menu power lancé"}
    if mode == "drun":
        spawn_detached(["wofi", "--show", "drun"])
        return {"ok": True, "mode": "drun", "message": "Lanceur d'applications Wofi lancé"}
    return {"ok": False, "error": f"Mode Wofi non supporté: {mode}"}


def _load_workspace_autocompact(compact_script: Path) -> Any:
    """Lazily loads workspace-autocompact.py once to preserve its in-process rules cache."""
    global _WAC_MODULE
    with _WAC_LOCK:
        if _WAC_MODULE is not None:
            return _WAC_MODULE
        spec = importlib.util.spec_from_file_location("workspace_autocompact", str(compact_script))
        if spec is None or spec.loader is None:
            raise ImportError(f"Impossible de charger {compact_script}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["workspace_autocompact"] = mod
        spec.loader.exec_module(mod)
        _WAC_MODULE = mod
        return mod


def compact_workspaces() -> Dict[str, Any]:
    """
    Triggers deterministic auto-compacting of workspaces across DP-1 and DP-2.
    Ensures bounds (DP-2: 1-5, DP-1: 6-10) without ghost gaps.
    """
    compact_script = DOTFILES_DIR / "hypr" / "scripts" / "workspace-autocompact.py"
    if not compact_script.exists():
        return {"ok": False, "error": "Script workspace-autocompact.py introuvable"}

    try:
        wac_mod = _load_workspace_autocompact(compact_script)
        changed = bool(wac_mod.compact_workspaces())
        return {
            "ok": True,
            "compacted": changed,
            "stdout": f"Compacted: {changed}",
            "stderr": "",
        }
    except (ImportError, OSError, AttributeError):
        res = _run_cmd([sys.executable, "-B", str(compact_script), "--once"], timeout=5.0)
        return {
            "ok": res["ok"],
            "stdout": res["stdout"],
            "stderr": res["stderr"],
        }
    except Exception as exc:
        return {
            "ok": False,
            "stdout": "",
            "stderr": str(exc),
        }


def switch_theme(theme: str) -> Dict[str, Any]:
    """
    Applies an ambient visual theme across Waybar, SwayNC, Wofi, Kitty, and Hyprland.
    Supported themes: aurora, tokyo-night, blackwall-red, cyberpunk-amber.
    """
    try:
        from theme_switcher import apply_theme
    except ImportError:
        from scripts.theme_switcher import apply_theme

    try:
        return apply_theme(theme)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
