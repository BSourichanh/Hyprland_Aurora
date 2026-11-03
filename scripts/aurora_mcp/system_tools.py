"""
Aurora MCP System Tools Module
Manages Hyprland IPC, DRM/GPU metrics, hardlink audits, session locking, and wallpaper engine.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
SCRIPTS_DIR = PROJECT_DIR / "scripts"
WALLPAPER_TOOL = SCRIPTS_DIR / "wallpaper_tool.py"
HYPRBAR_TOOL = SCRIPTS_DIR / "hyprbar"
LOCK_SCRIPT = DOTFILES_DIR / "hypr" / "lock.sh"


def _run_hyprctl(args: List[str]) -> Any:
    """Executes hyprctl with JSON flag."""
    try:
        res = subprocess.run(["hyprctl", "-j", *args], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    return None


def _check_hardlinks_dict() -> Dict[str, Any]:
    """Audits the hard links between dotfiles/ and ~/.config/."""
    mismatches = []
    missing = []
    checked = 0

    for root, _, files in os.walk(DOTFILES_DIR):
        for f in files:
            if f.endswith((".bak", "-bak", ".pyc", ".so")):
                continue
            dot_path = Path(root) / f
            rel = str(dot_path.relative_to(DOTFILES_DIR))
            conf_path = CONFIG_DIR / rel

            if not conf_path.exists():
                missing.append(rel)
                continue

            checked += 1
            try:
                if dot_path.stat().st_ino != conf_path.stat().st_ino:
                    mismatches.append(rel)
            except Exception:
                missing.append(rel)

    return {
        "total_checked": checked,
        "missing": missing,
        "mismatches": mismatches,
        "all_ok": len(mismatches) == 0 and len(missing) == 0
    }


def _get_gpu_info() -> Dict[str, Any]:
    """Retrieves Intel GPU metrics from /dev/shm shared memory or sysfs."""
    cache_file = Path("/dev/shm/waybar_gpu_cache.json")
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            if time.time() - data.get("ts", 0) <= 6.0:
                payload = data.get("payload", {})
                return {
                    "percentage": payload.get("percentage", 0),
                    "tooltip": payload.get("tooltip", ""),
                    "active": True
                }
        except Exception:
            pass

    freq_path = "/sys/class/drm/card1/gt_act_freq_mhz"
    if not os.path.exists(freq_path):
        freq_path = "/sys/class/drm/card0/gt_act_freq_mhz"
    freq = 0
    if os.path.exists(freq_path):
        try:
            freq = int(Path(freq_path).read_text().strip())
        except Exception:
            pass

    return {
        "percentage": 0,
        "frequency_mhz": freq,
        "active": False
    }


def _get_lock_info() -> Dict[str, Any]:
    """Checks session lock state."""
    flag_exists = Path("/tmp/hypr_locked").exists()
    hyprlock_active = False
    layers_data = _run_hyprctl(["layers"]) or {}
    for _, mdata in layers_data.items():
        for _, items in mdata.get("levels", {}).items():
            for it in items:
                if it.get("namespace") == "hyprlock":
                    hyprlock_active = True
                    break

    return {
        "locked": flag_exists or hyprlock_active,
        "flag_locked": flag_exists,
        "hyprlock_layer_active": hyprlock_active
    }


def manage_wallpaper(action: str, screen: Optional[str] = None) -> Dict[str, Any]:
    """
    Manages Wallpaper Engine (Lucy) processes and renderer.
    - action: 'status', 'restart', 'ensure', 'renderer_gpu', 'renderer_cpu', 'mask', 'sync'
    - screen: optional monitor target ('DP-1' or 'DP-2') for 'ensure' or 'restart'
    """
    cmd = [sys.executable, str(WALLPAPER_TOOL)]
    if action == "status":
        cmd.append("status")
    elif action == "restart":
        cmd.append("restart")
        if screen:
            cmd.extend(["--screen", screen])
    elif action == "ensure":
        cmd.append("ensure")
        if screen:
            cmd.extend(["--screen", screen])
    elif action == "renderer_gpu":
        cmd.extend(["renderer", "gpu"])
    elif action == "renderer_cpu":
        cmd.extend(["renderer", "cpu"])
    elif action == "mask":
        cmd.append("mask")
    elif action == "sync":
        cmd.append("sync")
    else:
        return {"ok": False, "error": f"Action inconnue: {action}"}

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    return {
        "ok": res.returncode == 0,
        "action": action,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }


def manage_hyprbar(action: str) -> Dict[str, Any]:
    """
    Controls Waybar and the Spotify ecosystem via hyprbar CLI.
    - action: 'restart' (full restart), 'reload' (CSS reload), 'toggle' (hide/show), 'status'
    """
    if action not in ("restart", "reload", "toggle", "status"):
        return {"ok": False, "error": f"Action non valide: {action}. Utiliser 'restart', 'reload', 'toggle' ou 'status'."}

    res = subprocess.run([str(HYPRBAR_TOOL), action], capture_output=True, text=True, timeout=10)
    return {
        "ok": res.returncode == 0,
        "action": action,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
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
        subprocess.Popen(["bash", str(LOCK_SCRIPT)])
        time.sleep(0.3)
        return {
            "ok": True,
            "action": "lock",
            "message": "Protocole de verrouillage lock.sh déclenché",
            "lock": _get_lock_info()
        }

    return {"ok": False, "error": f"Action lock inconnue: {action}. Utiliser 'lock' ou 'status'."}


def reload_all() -> Dict[str, Any]:
    """
    Performs an atomic full reload of the Aurora desktop ecosystem:
    - Hyprland configuration (hyprctl reload)
    - Waybar status bar (hyprbar restart)
    - SwayNC notification daemon (swaync-client -R && -rs)
    - Wallpaper Engine Lucy layer verification (wallpaper_tool.py ensure)
    - Hardlinks integrity audit (34/34 check)
    """
    if os.path.exists("/tmp/hypr_locked"):
        return {
            "ok": False,
            "error": "Session verrouillée (/tmp/hypr_locked actif). Rechargement ignoré par sécurité.",
            "actions": {}
        }

    results = {}

    res_hypr = subprocess.run(["hyprctl", "reload"], capture_output=True, text=True, timeout=5)
    results["hyprctl"] = {"ok": res_hypr.returncode == 0, "output": res_hypr.stdout.strip()}

    res_bar = subprocess.run([str(HYPRBAR_TOOL), "restart"], capture_output=True, text=True, timeout=8)
    results["waybar"] = {"ok": res_bar.returncode == 0, "output": res_bar.stdout.strip()}

    res_swaync = subprocess.run(["swaync-client", "-R"], capture_output=True, text=True, timeout=3)
    subprocess.run(["swaync-client", "-rs"], capture_output=True, text=True, timeout=3)
    results["swaync"] = {"ok": res_swaync.returncode == 0}

    res_wp = subprocess.run([sys.executable, str(WALLPAPER_TOOL), "ensure"], capture_output=True, text=True, timeout=5)
    results["wallpaper"] = {"ok": res_wp.returncode == 0, "output": res_wp.stdout.strip()}

    results["hardlinks"] = _check_hardlinks_dict()

    return {
        "ok": all(r.get("ok", False) for r in results.values()),
        "actions": results
    }


def audit_hardlinks() -> Dict[str, Any]:
    """
    Audits the integrity of the 34 hard links between dotfiles/ and ~/.config/.
    Ensures that modifications are directly reflected across inodes without broken links.
    """
    return _check_hardlinks_dict()


def wofi_launch(mode: str = "drun") -> Dict[str, Any]:
    """
    Launches Wofi in 'drun' (applications) or 'power' (power menu) mode.
    Runs asynchronously without blocking.
    """
    if mode == "power":
        script = DOTFILES_DIR / "hypr" / "scripts" / "power-menu.sh"
        subprocess.Popen(["bash", str(script)])
        return {"ok": True, "mode": "power", "message": "Menu power lancé"}
    elif mode == "drun":
        subprocess.Popen(["wofi", "--show", "drun"])
        return {"ok": True, "mode": "drun", "message": "Lanceur d'applications Wofi lancé"}
    else:
        return {"ok": False, "error": f"Mode Wofi non supporté: {mode}"}


def compact_workspaces() -> Dict[str, Any]:
    """
    Triggers deterministic auto-compacting of workspaces across DP-1 and DP-2.
    Ensures bounds (DP-2: 1-5, DP-1: 6-10) without ghost gaps.
    """
    compact_script = DOTFILES_DIR / "hypr" / "scripts" / "workspace-autocompact.py"
    if not compact_script.exists():
        return {"ok": False, "error": "Script workspace-autocompact.py introuvable"}

    res = subprocess.run([sys.executable, str(compact_script)], capture_output=True, text=True, timeout=5)
    return {
        "ok": res.returncode == 0,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }
