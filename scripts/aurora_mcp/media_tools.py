"""
Aurora MCP Media Tools Module
Manages Spotify MPRIS, PipeWire audio levels, SwayNC notification daemon and blacklists.
"""

import contextlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from aurora_runtime import file_mutex, get_aurora_runtime_dir  # noqa: E402

PROJECT_DIR = SCRIPTS_DIR.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
BLACKLIST_TOOL = DOTFILES_DIR / "swaync" / "scripts" / "blacklist-app.py"
SWAYNC_CONFIG = CONFIG_DIR / "swaync" / "config.json"


def _safe_run(cmd: List[str], timeout: float = 3.0) -> Dict[str, Any]:
    """Executes subprocess isolated from MCP stdio with timeout and OSError guards."""
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
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"Timeout ({timeout}s)"}
    except (FileNotFoundError, OSError) as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc)}


def _get_spotify_info() -> Dict[str, Any]:
    """Retrieves current Spotify playback information via MPRIS."""
    info = {"status": "Stopped", "track": "", "artist": "", "album": "", "position": "", "running": False}
    status_res = _safe_run(["playerctl", "--player=spotify", "status"], timeout=2.0)
    if not status_res["ok"]:
        return info

    info["status"] = status_res["stdout"]
    info["running"] = True

    meta_res = _safe_run(
        [
            "playerctl",
            "--player=spotify",
            "metadata",
            "--format",
            "{{artist}} - {{title}}||{{album}}||{{position}}||{{mpris:length}}",
        ],
        timeout=2.0,
    )
    if meta_res["ok"] and "||" in meta_res["stdout"]:
        parts = meta_res["stdout"].split("||")
        track_str = parts[0]
        if " - " in track_str:
            info["artist"], info["track"] = track_str.split(" - ", 1)
        else:
            info["track"] = track_str
        if len(parts) > 1:
            info["album"] = parts[1]
        if len(parts) > 3 and parts[2] and parts[3]:
            with contextlib.suppress(Exception):
                pos_s = int(parts[2]) // 1000000
                len_s = int(parts[3]) // 1000000
                info["position"] = f"{pos_s // 60:02d}:{pos_s % 60:02d} / {len_s // 60:02d}:{len_s % 60:02d}"
    return info


def _get_swaync_info() -> Dict[str, Any]:
    """Retrieves SwayNC notification status and DND state."""
    count = 0
    dnd = False
    running = False

    c_res = _safe_run(["swaync-client", "-c"], timeout=2.0)
    if c_res["ok"] and c_res["stdout"].isdigit():
        count = int(c_res["stdout"])
        running = True

    d_res = _safe_run(["swaync-client", "-D"], timeout=2.0)
    if d_res["ok"]:
        dnd = d_res["stdout"].lower() == "true"

    return {
        "running": running,
        "notification_count": count,
        "dnd_enabled": dnd,
    }


def _get_audio_info() -> Dict[str, Any]:
    """Retrieves PipeWire / WirePlumber volume and mute status via wpctl."""
    sink_info = {"volume_pct": 0, "muted": False}
    source_info = {"volume_pct": 0, "muted": False}

    for node, target in (("@DEFAULT_AUDIO_SINK@", sink_info), ("@DEFAULT_AUDIO_SOURCE@", source_info)):
        res = _safe_run(["wpctl", "get-volume", node], timeout=2.0)
        if res["ok"]:
            out = res["stdout"]
            parts = out.split()
            if len(parts) >= 2:
                with contextlib.suppress(ValueError):
                    target["volume_pct"] = int(round(float(parts[1]) * 100))
            target["muted"] = "[MUTED]" in out

    return {"sink": sink_info, "source": source_info}


def manage_swaync(action: str) -> Dict[str, Any]:
    """
    Controls the SwayNC notification center daemon.
    - action: 'status', 'toggle_dnd', 'clear', 'reload', 'close_latest'
    """
    if action == "status":
        return {"ok": True, "action": action, "swaync": _get_swaync_info()}

    cmd_map = {
        "toggle_dnd": ["swaync-client", "-d"],
        "clear": ["swaync-client", "-C"],
        "reload": ["swaync-client", "-R"],
        "close_latest": ["swaync-client", "-cl"],
    }
    cmd = cmd_map.get(action)
    if not cmd:
        return {"ok": False, "error": f"Action SwayNC non supportée: {action}."}

    res = _safe_run(cmd, timeout=5.0)
    if action == "reload" and res["ok"]:
        css_res = _safe_run(["swaync-client", "-rs"], timeout=3.0)
        res["ok"] = res["ok"] and css_res["ok"]

    return {
        "ok": res["ok"],
        "action": action,
        "swaync": _get_swaync_info(),
        **({"error": res["stderr"]} if not res["ok"] and res["stderr"] else {}),
    }


def _extract_exact_pattern_name(pattern: str) -> str:
    """Extracts plain literal app/entry name from ^(?i)...$ regex rules."""
    cleaned = str(pattern)
    if cleaned.startswith("^(?i)") and cleaned.endswith("$"):
        cleaned = cleaned[5:-1].replace("\\", "")
    return cleaned.lower().strip()


def manage_blacklist(action: str, target: Optional[str] = None) -> Dict[str, Any]:
    """
    Manages the notification blacklist in ~/.config/swaync/config.json under flock.
    - action: 'list', 'add', 'remove'
    - target: exact application name or rule key (required for 'add' and 'remove')
    """
    if not SWAYNC_CONFIG.exists():
        return {"ok": False, "error": "Fichier config.json de SwayNC introuvable"}

    if action == "list":
        try:
            with open(SWAYNC_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            rules = data.get("notification-visibility", {})
            return {"ok": True, "action": "list", "rules_count": len(rules), "rules": rules}
        except Exception as exc:
            return {"ok": False, "error": f"Erreur lecture config: {exc}"}

    if not target or not target.strip():
        return {"ok": False, "error": "Le paramètre 'target' est obligatoire pour 'add' et 'remove'"}

    target = target.strip()
    lock_path = get_aurora_runtime_dir() / "swaync_blacklist.lock"

    if action == "add":
        if not BLACKLIST_TOOL.exists():
            return {"ok": False, "error": "Script blacklist-app.py introuvable"}
        with file_mutex(lock_path, non_blocking=False) as acquired:
            if not acquired:
                return {"ok": False, "error": "Impossible d'acquérir le verrou blacklist"}
            res = _safe_run([sys.executable, "-B", str(BLACKLIST_TOOL), target, target, target], timeout=5.0)
        return {
            "ok": res["ok"],
            "action": "add",
            "target": target,
            "stdout": res["stdout"],
            "stderr": res["stderr"],
        }

    if action == "remove":
        try:
            removed_keys: List[str] = []
            with file_mutex(lock_path, non_blocking=False) as acquired:
                if not acquired:
                    return {"ok": False, "error": "Impossible d'acquérir le verrou blacklist"}
                with open(SWAYNC_CONFIG, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    rules = data.get("notification-visibility", {})
                    target_lower = target.lower()
                    norm_target = re.sub(r"[^a-zA-Z0-9_-]", "-", target_lower).strip("-")
                    exact_keys = {
                        target_lower,
                        norm_target,
                        f"blacklist-app-{norm_target}",
                        f"blacklist-entry-{norm_target}",
                        f"blacklist-snap-{norm_target}",
                    }
                    keys_to_del = [
                        k
                        for k, v in rules.items()
                        if k.lower() in exact_keys
                        or _extract_exact_pattern_name(v.get("app-name", "")) == target_lower
                        or _extract_exact_pattern_name(v.get("desktop-entry", "")) == target_lower
                    ]
                    for k in keys_to_del:
                        del rules[k]
                        removed_keys.append(k)
                    if removed_keys:
                        f.seek(0)
                        json.dump(data, f, indent=2)
                        f.truncate()

            if removed_keys:
                _safe_run(["swaync-client", "-R"], timeout=3.0)

            return {"ok": True, "action": "remove", "target": target, "removed_rules": removed_keys}
        except Exception as exc:
            return {"ok": False, "error": f"Erreur suppression blacklist: {exc}"}

    return {"ok": False, "error": f"Action blacklist non supportée: {action}. Utiliser 'list', 'add', ou 'remove'."}


def audio_control(action: str, value: Optional[str] = None) -> Dict[str, Any]:
    """
    Controls PipeWire / WirePlumber audio volume and muting via wpctl.
    - action: 'status', 'volume_up', 'volume_down', 'mute_toggle', 'mic_mute_toggle', 'set_volume'
    - value: volume value for 'set_volume' (e.g. '0.8', '80%', '1%')
    """
    if action == "status":
        return {"ok": True, "audio": _get_audio_info()}

    cmd: Optional[List[str]] = None
    if action == "volume_up":
        cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", "5%+"]
    elif action == "volume_down":
        cmd = ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"]
    elif action == "mute_toggle":
        cmd = ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
    elif action == "mic_mute_toggle":
        cmd = ["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]
    elif action == "set_volume":
        if not value or not value.strip():
            return {"ok": False, "error": "Le paramètre 'value' est requis pour set_volume (ex: '0.8' ou '80%')"}
        raw = value.strip()
        is_pct = raw.endswith("%")
        val = raw[:-1].strip() if is_pct else raw
        try:
            num = float(val)
        except ValueError:
            return {"ok": False, "error": f"Valeur de volume invalide: {value}"}
        if not math.isfinite(num) or num < 0.0:
            return {"ok": False, "error": f"Valeur de volume hors bornes: {value}"}
        if is_pct:
            num = num / 100.0
        elif num > 1.5:
            num = num / 100.0
        if num > 1.5:
            return {"ok": False, "error": f"Volume maximal dépassé (max 150% / 1.5): {value}"}
        cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", f"{num:.4f}".rstrip("0").rstrip(".") or "0"]
    else:
        return {"ok": False, "error": f"Action audio inconnue: {action}"}

    res = _safe_run(cmd, timeout=3.0)
    return {
        "ok": res["ok"],
        "action": action,
        "audio": _get_audio_info(),
        **({"error": res["stderr"]} if not res["ok"] and res["stderr"] else {}),
    }


def spotify_control(command: str) -> Dict[str, Any]:
    """
    Controls Spotify playback via MPRIS D-Bus.
    - command: 'play_pause', 'next', 'previous', 'status'
    """
    cmd_map = {
        "play_pause": "play-pause",
        "next": "next",
        "previous": "previous",
        "status": "status",
    }
    sub = cmd_map.get(command)
    if not sub:
        return {"ok": False, "error": f"Commande Spotify inconnue: {command}"}

    if command == "status":
        return {"ok": True, "spotify": _get_spotify_info()}

    res = _safe_run(["playerctl", "--player=spotify", sub], timeout=3.0)
    time.sleep(0.15)
    return {
        "ok": res["ok"],
        "command": command,
        "spotify": _get_spotify_info(),
        **({"error": res["stderr"]} if not res["ok"] and res["stderr"] else {}),
    }
