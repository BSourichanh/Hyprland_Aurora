#!/usr/bin/env python3
"""Native GTK3 LayerShell OSD (volume, mic, Caps Lock) adhering to Aurora Theme."""

import fcntl
import glob
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Tuple

_REPO_HYPR = Path(__file__).resolve().parent.parent / "dotfiles" / "hypr" / "scripts"
_CFG_HYPR = Path.home() / ".config" / "hypr" / "scripts"
for _p in (_REPO_HYPR, _CFG_HYPR):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from hypr_ipc import get_aurora_runtime_dir, hypr_json, is_session_locked

RUNTIME_DIR = get_aurora_runtime_dir()
SOCK_PATH = str(RUNTIME_DIR / "aurora_osd.sock")
LOCK_PATH = str(RUNTIME_DIR / "aurora_osd.lock")
SELF_PATH = str(Path(__file__).resolve())
_lock_fd = None

# AURORA_PALETTE_START
AURORA_OSD_CSS = (
    b"window { background-color: transparent; }\n"
    b".osd-pill { background-color: rgba(10, 15, 30, 0.50); border: 2px solid #00f0ff;"
    b" border-radius: 17px; padding: 12px 20px; }\n"
    b".osd-icon { color: #00f0ff; font-family: 'JetBrainsMono Nerd Font', 'Symbols Nerd Font', sans-serif;"
    b" font-size: 20px; min-width: 28px; }\n"
    b".osd-label { color: #e1e4f1; font-family: 'Noto Sans', sans-serif; font-size: 14px;"
    b" font-weight: bold; min-width: 118px; }\n"
    b".osd-muted .osd-icon, .osd-muted .osd-label { color: #94a3b8; }\n"
    b"progressbar trough { background-color: rgba(148, 163, 184, 0.22); border-radius: 6px;"
    b" min-height: 8px; min-width: 150px; }\n"
    b"progressbar progress { background-image: linear-gradient(45deg, #00f0ff, #7aa2f7, #9778d0);"
    b" border-radius: 6px; min-height: 8px; }\n"
    b".osd-overdrive progressbar progress { background-image: linear-gradient(45deg, #f7768e, #ff9e64, #e0af68); }\n"
    b".osd-muted progressbar progress { background-image: none; background-color: #64748b; }\n"
)
# AURORA_PALETTE_END

_WPCTL_CMDS = {
    "volume-up": ("volume", "@DEFAULT_AUDIO_SINK@", ["set-volume", "-l", "1.5", "@DEFAULT_AUDIO_SINK@", "5%+"]),
    "volume-down": ("volume", "@DEFAULT_AUDIO_SINK@", ["set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"]),
    "volume-mute": ("volume", "@DEFAULT_AUDIO_SINK@", ["set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]),
    "mic-mute": ("mic", "@DEFAULT_AUDIO_SOURCE@", ["set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"]),
}


def _parse_wpctl(target: str) -> Tuple[int, bool]:
    """Queries wpctl volume percentage and mute state for a PipeWire node."""
    try:
        res = subprocess.run(["wpctl", "get-volume", target], capture_output=True, text=True, timeout=1.0, check=False)
        out = res.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return 0, False
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", out)
    return (int(round(float(match.group(1)) * 100)) if match else 0), ("[MUTED]" in out)


def _read_capslock() -> bool:
    """Queries Hyprland j/devices capsLock state, falling back to kernel LED sysfs."""
    devs = hypr_json("j/devices", timeout=0.05)
    if isinstance(devs, dict) and devs.get("keyboards"):
        kbs = [k for k in devs["keyboards"] if isinstance(k, dict)]
        main_kbs = [k for k in kbs if k.get("main")]
        if main_kbs:
            return any(bool(k.get("capsLock")) for k in main_kbs)
        if kbs:
            return any(bool(k.get("capsLock")) for k in kbs)
    time.sleep(0.035)
    for path in sorted(glob.glob("/sys/class/leds/*::capslock/brightness")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                if f.read().strip() == "1":
                    return True
        except OSError:
            continue
    return False


def _volume_icon(pct: int, muted: bool) -> str:
    if muted:
        return "󰝟"
    return "󰕿" if pct < 35 else ("󰖀" if pct < 70 else "󰕾")


def handle_action(action: str) -> Dict[str, Any]:
    """Applies the requested audio or Caps Lock action and builds the OSD payload."""
    spec = _WPCTL_CMDS.get(action)
    if spec is not None:
        kind, target, args = spec
        subprocess.run(["wpctl", *args], check=False)
        pct, muted = _parse_wpctl(target)
        fraction = 0.0 if muted else min(1.0, pct / 100.0)
        if kind == "mic":
            icon = "󰍭" if muted else "󰍬"
            label = "Micro coupé" if muted else f"Micro actif ({pct}%)"
        else:
            icon = _volume_icon(pct, muted)
            label = "Muet" if muted else f"{pct}%"
        return {"kind": kind, "icon": icon, "label": label, "fraction": fraction, "muted": muted,
                "overdrive": (pct > 100 and not muted)}
    if action == "caps-lock":
        on = _read_capslock()
        return {"kind": "caps", "icon": "󰪛",
                "label": "Verr. Maj activé" if on else "Verr. Maj désactivé",
                "fraction": 1.0 if on else 0.0, "muted": not on, "overdrive": False}
    raise ValueError(f"Unsupported OSD action: {action}")


def send_payload(payload: Dict[str, Any]) -> bool:
    """Sends a JSON OSD payload to the active UNIX socket daemon."""
    raw = (json.dumps(payload) + "\n").encode("utf-8")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.15)
            sock.connect(SOCK_PATH)
            sock.sendall(raw)
        return True
    except OSError:
        return False


def ensure_and_send(payload: Dict[str, Any]) -> bool:
    """Sends payload to daemon, auto-starting the daemon if not yet running."""
    if send_payload(payload):
        return True
    subprocess.Popen(
        [sys.executable, "-B", SELF_PATH, "daemon"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(15):
        time.sleep(0.03)
        if os.path.exists(SOCK_PATH) and send_payload(payload):
            return True
    return False


def _acquire_daemon_lock() -> bool:
    """Acquires non-blocking singleton lock with strict 0600 permissions."""
    global _lock_fd
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    os.chmod(LOCK_PATH, 0o600)
    f = os.fdopen(fd, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _lock_fd = f
    return True


def run_daemon() -> int:
    """Starts the LayerShell GTK3 OSD overlay daemon listening on $AURORA_RUNTIME_DIR."""
    if not _acquire_daemon_lock():
        return 0

    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell

    provider = Gtk.CssProvider()
    provider.load_from_data(AURORA_OSD_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_decorated(False)
    win.set_resizable(False)
    win.set_app_paintable(True)
    if visual := win.get_screen().get_rgba_visual():
        win.set_visual(visual)

    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_namespace(win, "aurora-osd")
    GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.BOTTOM, True)
    GtkLayerShell.set_margin(win, GtkLayerShell.Edge.BOTTOM, 64)
    GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)

    pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
    pill.get_style_context().add_class("osd-pill")
    icon_lbl = Gtk.Label(label="󰕾")
    icon_lbl.get_style_context().add_class("osd-icon")
    bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER)
    bar.set_no_show_all(True)
    text_lbl = Gtk.Label(label="50%", xalign=1.0)
    text_lbl.get_style_context().add_class("osd-label")
    pill.pack_start(icon_lbl, False, False, 0)
    pill.pack_start(bar, True, True, 0)
    pill.pack_start(text_lbl, False, False, 0)
    icon_lbl.show(); text_lbl.show(); pill.show()
    win.add(pill)

    hide_timer_id = 0

    def hide_osd() -> bool:
        nonlocal hide_timer_id
        hide_timer_id = 0
        win.hide()
        return False

    def show_osd(payload: Dict[str, Any]) -> bool:
        nonlocal hide_timer_id
        if is_session_locked():
            return False
        icon_lbl.set_text(str(payload.get("icon", "󰕾")))
        text_lbl.set_text(str(payload.get("label", "")))
        bar.set_fraction(max(0.0, min(1.0, float(payload.get("fraction", 0.0)))))
        ctx = pill.get_style_context()
        ctx.add_class("osd-muted") if payload.get("muted") else ctx.remove_class("osd-muted")
        ctx.add_class("osd-overdrive") if payload.get("overdrive") else ctx.remove_class("osd-overdrive")
        win.show_all()
        bar.set_visible(payload.get("kind") != "caps")
        if hide_timer_id:
            GLib.source_remove(hide_timer_id)
        hide_timer_id = GLib.timeout_add(1500, hide_osd)
        return False

    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK_PATH)
    os.chmod(SOCK_PATH, 0o600)
    srv.listen(8)

    def listen_loop() -> None:
        while True:
            try:
                conn, _ = srv.accept()
                with conn:
                    raw = conn.recv(2048).decode("utf-8", errors="replace").strip()
                for line in raw.splitlines():
                    if line:
                        GLib.idle_add(show_osd, json.loads(line))
            except (OSError, json.JSONDecodeError, ValueError):
                continue

    threading.Thread(target=listen_loop, daemon=True).start()
    Gtk.main()
    return 0


def main() -> int:
    """CLI entry point for aurora-osd daemon and immediate actions."""
    if len(sys.argv) != 2:
        print("Usage: aurora-osd <daemon|volume-up|volume-down|volume-mute|mic-mute|caps-lock>", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "daemon":
        return run_daemon()
    try:
        payload = handle_action(cmd)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    ensure_and_send(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
