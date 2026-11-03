"""
Aurora MCP Media Tools Module
Manages Spotify MPRIS, PipeWire audio levels, SwayNC notification daemon and blacklists.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DOTFILES_DIR = PROJECT_DIR / "dotfiles"
CONFIG_DIR = Path(os.path.expanduser("~/.config"))
BLACKLIST_TOOL = DOTFILES_DIR / "swaync" / "scripts" / "blacklist-app.py"
SWAYNC_CONFIG = CONFIG_DIR / "swaync" / "config.json"


def _get_spotify_info() -> Dict[str, Any]:
    """Retrieves current Spotify playback information via MPRIS."""
    info = {"status": "Stopped", "track": "", "artist": "", "album": "", "position": "", "running": False}
    try:
        status_res = subprocess.run(["playerctl", "--player=spotify", "status"], capture_output=True, text=True, timeout=2)
        if status_res.returncode == 0:
            info["status"] = status_res.stdout.strip()
            info["running"] = True

            meta_res = subprocess.run(
                ["playerctl", "--player=spotify", "metadata", "--format", "{{artist}} - {{title}}||{{album}}||{{position}}||{{mpris:length}}"],
                capture_output=True, text=True, timeout=2
            )
            if meta_res.returncode == 0 and "||" in meta_res.stdout:
                parts = meta_res.stdout.strip().split("||")
                track_str = parts[0]
                if " - " in track_str:
                    info["artist"], info["track"] = track_str.split(" - ", 1)
                else:
                    info["track"] = track_str
                if len(parts) > 1:
                    info["album"] = parts[1]
                if len(parts) > 3 and parts[2] and parts[3]:
                    try:
                        pos_s = int(parts[2]) // 1000000
                        len_s = int(parts[3]) // 1000000
                        info["position"] = f"{pos_s // 60:02d}:{pos_s % 60:02d} / {len_s // 60:02d}:{len_s % 60:02d}"
                    except Exception:
                        pass
    except Exception:
        pass
    return info


def _get_swaync_info() -> Dict[str, Any]:
    """Retrieves SwayNC notification status and DND state."""
    count = 0
    dnd = False
    running = False
    try:
        c_res = subprocess.run(["swaync-client", "-c"], capture_output=True, text=True, timeout=2)
        if c_res.returncode == 0:
            count = int(c_res.stdout.strip())
            running = True

        d_res = subprocess.run(["swaync-client", "-D"], capture_output=True, text=True, timeout=2)
        if d_res.returncode == 0:
            dnd = d_res.stdout.strip().lower() == "true"
    except Exception:
        pass

    return {
        "running": running,
        "notification_count": count,
        "dnd_enabled": dnd
    }


def _get_audio_info() -> Dict[str, Any]:
    """Retrieves PipeWire / WirePlumber volume and mute status via wpctl."""
    sink_info = {"volume_pct": 0, "muted": False}
    source_info = {"volume_pct": 0, "muted": False}

    try:
        res = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            out = res.stdout.strip()
            parts = out.split()
            if len(parts) >= 2:
                sink_info["volume_pct"] = int(round(float(parts[1]) * 100))
            sink_info["muted"] = "[MUTED]" in out
    except Exception:
        pass

    try:
        res_src = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"], capture_output=True, text=True, timeout=2)
        if res_src.returncode == 0:
            out = res_src.stdout.strip()
            parts = out.split()
            if len(parts) >= 2:
                source_info["volume_pct"] = int(round(float(parts[1]) * 100))
            source_info["muted"] = "[MUTED]" in out
    except Exception:
        pass

    return {
        "sink": sink_info,
        "source": source_info
    }


def manage_swaync(action: str) -> Dict[str, Any]:
    """
    Controls the SwayNC notification center daemon.
    - action: 'status' (count and DND state), 'toggle_dnd' (toggle Do Not Disturb),
              'clear' (clear all notifications), 'reload' (reload config JSON and CSS),
              'close_latest' (close latest floating popup)
    """
    if action == "status":
        return {"ok": True, "action": action, "swaync": _get_swaync_info()}

    cmd_map = {
        "toggle_dnd": ["swaync-client", "-d"],
        "clear": ["swaync-client", "-C"],
        "reload": ["swaync-client", "-R"],
        "close_latest": ["swaync-client", "-cl"]
    }

    cmd = cmd_map.get(action)
    if not cmd:
        return {"ok": False, "error": f"Action SwayNC non supportée: {action}. Utiliser 'status', 'toggle_dnd', 'clear', 'reload', ou 'close_latest'."}

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if action == "reload":
        subprocess.run(["swaync-client", "-rs"], capture_output=True, text=True, timeout=3)

    return {
        "ok": res.returncode == 0,
        "action": action,
        "swaync": _get_swaync_info()
    }


def manage_blacklist(action: str, target: Optional[str] = None) -> Dict[str, Any]:
    """
    Manages the notification blacklist in ~/.config/swaync/config.json.
    - action: 'list' (list blacklisted apps/rules), 'add' (blacklist an application name),
              'remove' (remove application rules by key or name)
    - target: application name or rule key (required for 'add' and 'remove')
    """
    if not SWAYNC_CONFIG.exists():
        return {"ok": False, "error": "Fichier config.json de SwayNC introuvable"}

    if action == "list":
        try:
            with open(SWAYNC_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            rules = data.get("notification-visibility", {})
            return {
                "ok": True,
                "action": "list",
                "rules_count": len(rules),
                "rules": rules
            }
        except Exception as e:
            return {"ok": False, "error": f"Erreur lecture config: {e}"}

    if not target or not target.strip():
        return {"ok": False, "error": "Le paramètre 'target' est obligatoire pour 'add' et 'remove'"}

    target = target.strip()

    if action == "add":
        if not BLACKLIST_TOOL.exists():
            return {"ok": False, "error": "Script blacklist-app.py introuvable"}
        res = subprocess.run([sys.executable, str(BLACKLIST_TOOL), target, target, target], capture_output=True, text=True, timeout=5)
        return {
            "ok": res.returncode == 0,
            "action": "add",
            "target": target,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }

    if action == "remove":
        try:
            removed_keys = []
            with open(SWAYNC_CONFIG, "r+", encoding="utf-8") as f:
                data = json.load(f)
                rules = data.get("notification-visibility", {})
                norm_target = re.sub(r"[^a-zA-Z0-9_-]", "-", target.lower()).strip("-")
                keys_to_del = [
                    k for k, v in rules.items()
                    if norm_target in k.lower() or target.lower() in str(v.get("app-name", "")).lower() or target.lower() in str(v.get("desktop-entry", "")).lower()
                ]

                for k in keys_to_del:
                    del rules[k]
                    removed_keys.append(k)

                if removed_keys:
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()

            if removed_keys:
                subprocess.run(["swaync-client", "-R"], check=False)

            return {
                "ok": True,
                "action": "remove",
                "target": target,
                "removed_rules": removed_keys
            }
        except Exception as e:
            return {"ok": False, "error": f"Erreur suppression blacklist: {e}"}

    return {"ok": False, "error": f"Action blacklist non supportée: {action}. Utiliser 'list', 'add', ou 'remove'."}


def audio_control(action: str, value: Optional[str] = None) -> Dict[str, Any]:
    """
    Controls PipeWire / WirePlumber audio volume and muting via wpctl.
    - action: 'status' (volume and mute info), 'volume_up' (+5%), 'volume_down' (-5%),
              'mute_toggle' (toggle sink mute), 'mic_mute_toggle' (toggle source mute),
              'set_volume' (set sink volume to specific float or percentage)
    - value: volume value for 'set_volume' (e.g. '0.8', '80%')
    """
    if action == "status":
        return {"ok": True, "audio": _get_audio_info()}

    cmd = None
    if action == "volume_up":
        cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", "5%+"]
    elif action == "volume_down":
        cmd = ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"]
    elif action == "mute_toggle":
        cmd = ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
    elif action == "mic_mute_toggle":
        cmd = ["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]
    elif action == "set_volume":
        if not value:
            return {"ok": False, "error": "Le paramètre 'value' est requis pour set_volume (ex: '0.8' ou '80%')"}
        val = value.strip().rstrip("%")
        try:
            num = float(val)
            if num > 1.5:
                num = num / 100.0
            cmd = ["wpctl", "set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", str(num)]
        except ValueError:
            return {"ok": False, "error": f"Valeur de volume invalide: {value}"}
    else:
        return {"ok": False, "error": f"Action audio inconnue: {action}"}

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
    return {
        "ok": res.returncode == 0,
        "action": action,
        "audio": _get_audio_info()
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
        "status": "status"
    }
    sub = cmd_map.get(command)
    if not sub:
        return {"ok": False, "error": f"Commande Spotify inconnue: {command}"}

    if command == "status":
        return {"ok": True, "spotify": _get_spotify_info()}

    res = subprocess.run(["playerctl", "--player=spotify", sub], capture_output=True, text=True, timeout=3)
    time.sleep(0.15)
    return {
        "ok": res.returncode == 0,
        "command": command,
        "spotify": _get_spotify_info()
    }
