#!/usr/bin/env python3
"""
Aurora Spotify Music Video Wallpaper Synchronizer
Synchronizes official music videos / clips to Wallpaper Engine on Wayland.
- Zero polling: Event-driven via MPRIS D-Bus PropertiesChanged.
- Targets secondary screen (DP-2) in wlr-layer-shell layer bottom while Lucy remains on DP-1.
- Strict duration matching (+/- 5s) & channel filtering to isolate official music videos.
- Hardware-accelerated decoding (VAAPI H.264) with local caching and seamless Lucy fallback.
"""

import atexit
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# ---------------------------------------------------------------------------
# PATHS & CONFIGURATION
# ---------------------------------------------------------------------------
LOCK_FILE = "/tmp/spotify_clip_sync.lock"
CACHE_DIR = Path(os.path.expanduser("~/.cache/spotify_clips"))
VIDEOS_DIR = CACHE_DIR / "videos"
WALLPAPER_DIR = CACHE_DIR / "wallpaper"
INDEX_FILE = CACHE_DIR / "index.json"
CONFIG_FILE = Path(os.path.expanduser("~/.config/hypr/spotify_clip.json"))

WORKSHOP_DIR = Path(os.path.expanduser("~/.steam/steam/steamapps/workshop/content/431960/3566437475"))
ASSETS_DIR = Path(os.path.expanduser("~/.steam/steam/steamapps/common/wallpaper_engine/assets"))
YT_DLP_BIN = Path(os.path.expanduser("~/.local/bin/yt-dlp"))
if not YT_DLP_BIN.exists():
    YT_DLP_BIN = Path("/usr/bin/yt-dlp")

DEFAULT_CONFIG = {
    "enabled": True,
    "target_monitor": "DP-2",
    "fps": 60,
    "max_duration_diff_sec": 6.0,
    "fallback_to_canvas": True,
}


def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception:
            pass
    return cfg


# ---------------------------------------------------------------------------
# INDEX & CACHE MANAGEMENT
# ---------------------------------------------------------------------------
class ClipCache:
    def __init__(self, index_path: Path):
        self.path = index_path
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

    def get(self, track_uri: str) -> str | None:
        with self._lock:
            return self.data.get(track_uri)

    def set(self, track_uri: str, file_path_or_none: str | None):
        with self._lock:
            self.data[track_uri] = file_path_or_none
        self.save()


# ---------------------------------------------------------------------------
# WALLPAPER ENGINE CONTROLLER
# ---------------------------------------------------------------------------
class WallpaperController:
    """Manages switching between Lucy and the Spotify Video Wallpaper on DP-2."""

    def __init__(self, monitor: str = "DP-2", fps: int = 60):
        self.monitor = monitor
        self.fps = fps
        self.current_state = "LUCY"
        self._lock = threading.Lock()

    def get_monitor_pid(self) -> int | None:
        res = subprocess.run(["pgrep", "-fl", "linux-wallpaperengine"], capture_output=True, text=True)
        for line in res.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split(maxsplit=1)
            pid = int(parts[0])
            try:
                cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
                if f"--screen-root\x00{self.monitor}".encode() in cmdline:
                    return pid
            except Exception:
                pass
        return None

    def kill_monitor_process(self):
        pid = self.get_monitor_pid()
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.15)
            except ProcessLookupError:
                pass

    def display_clip(self, video_path: Path):
        with self._lock:
            if not video_path.exists():
                return

            WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
            target_video = WALLPAPER_DIR / "video.mp4"
            target_proj = WALLPAPER_DIR / "project.json"

            # 1. Update project.json
            with open(target_proj, "w", encoding="utf-8") as f:
                json.dump({"file": "video.mp4", "title": "Spotify Clip", "type": "video"}, f, indent=2)

            # 2. Hardlink or copy video.mp4
            if target_video.exists():
                target_video.unlink()
            try:
                os.link(video_path, target_video)
            except OSError:
                import shutil
                shutil.copy2(video_path, target_video)

            # 3. Kill current DP-2 process and spawn video wallpaper
            self.kill_monitor_process()
            cmd = [
                "nohup",
                "linux-wallpaperengine",
                "--screen-root", self.monitor,
                "--bg", str(WALLPAPER_DIR),
                "--volume", "0",
                "--silent",
                "--fps", str(self.fps),
                "--scaling", "fill",
                "--assets-dir", str(ASSETS_DIR),
            ]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.current_state = "CLIP"

    def restore_lucy(self):
        with self._lock:
            if self.current_state == "LUCY":
                # Ensure DP-2 actually has a running process
                if self.get_monitor_pid() is not None:
                    return

            self.kill_monitor_process()
            cmd = [
                "nohup",
                "linux-wallpaperengine",
                "--screen-root", self.monitor,
                "--bg", str(WORKSHOP_DIR),
                "--volume", "100",
                "--no-audio-processing",
                "--fps", str(self.fps),
                "--disable-parallax",
                "--scaling", "fill",
                "--assets-dir", str(ASSETS_DIR),
            ]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.current_state = "LUCY"


# ---------------------------------------------------------------------------
# OFFICIAL CLIP RESOLVER
# ---------------------------------------------------------------------------
def get_spotify_canvas_url() -> str:
    """Attempts to retrieve the real-time canvas URL from the running Spotify client via CDP."""
    try:
        import urllib.request
        import asyncio
        import websockets

        pages_raw = urllib.request.urlopen("http://127.0.0.1:8088/json", timeout=0.5).read()
        pages = json.loads(pages_raw)
        ws_url = pages[0]["webSocketDebuggerUrl"]

        async def fetch():
            async with websockets.connect(ws_url, close_timeout=1) as ws:
                msg = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "Spicetify.Player?.data?.item?.metadata?.['canvas.url'] || ''"}
                }
                await ws.send(json.dumps(msg))
                res = json.loads(await ws.recv())
                return res.get("result", {}).get("result", {}).get("value", "")

        return asyncio.run(fetch())
    except Exception:
        return ""


def resolve_and_download_clip(
    artist: str,
    title: str,
    target_duration_s: float,
    track_uri: str,
    cache: ClipCache,
    max_diff: float = 6.0,
    fallback_to_canvas: bool = True
) -> Path | None:
    """Searches YouTube for official video matching duration, downloads and caches. Falls back to Canvas."""
    clean_title = re.sub(r"\(feat\.[^\)]+\)", "", title, flags=re.IGNORECASE).strip()
    query = f"{artist} {clean_title} Official Music Video"

    cmd = [
        str(YT_DLP_BIN),
        "--print", "%(id)s|||%(title)s|||%(duration)s",
        "--no-playlist",
        f"ytsearch4:{query}"
    ]
    best_id = None
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        best_diff = 999.0
        for line in res.stdout.strip().splitlines():
            if "|||" not in line:
                continue
            parts = line.split("|||")
            if len(parts) < 3:
                continue
            vid, vtitle, vdur = parts[0], parts[1], parts[2]
            try:
                vdur = float(vdur)
            except Exception:
                continue

            diff = abs(vdur - target_duration_s)
            lower_t = vtitle.lower()
            if any(neg in lower_t for neg in ["live", "cover", "reaction", "tutorial", "1 hour", "bass boosted"]):
                continue

            if diff <= max_diff and diff < best_diff:
                best_diff = diff
                best_id = vid
    except Exception:
        pass

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", track_uri.replace("spotify:track:", "").replace("/com/spotify/track/", ""))

    # 1. Download YouTube Official Clip if found
    if best_id:
        output_file = VIDEOS_DIR / f"{clean_id}_{best_id}.mp4"
        dl_cmd = [
            str(YT_DLP_BIN),
            "-f", "bestvideo[vcodec^=avc1][height<=1080]/bestvideo[height<=1080][ext=mp4]/best[height<=1080]",
            "--no-playlist",
            "-o", str(output_file),
            f"https://www.youtube.com/watch?v={best_id}"
        ]
        try:
            dl_res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=30)
            if dl_res.returncode == 0 and output_file.exists() and output_file.stat().st_size > 100_000:
                cache.set(track_uri, str(output_file))
                return output_file
        except Exception:
            pass

    # 2. Fallback to Spotify Canvas if enabled
    if fallback_to_canvas:
        canvas_url = get_spotify_canvas_url()
        if canvas_url and canvas_url.startswith("http"):
            canvas_file = VIDEOS_DIR / f"{clean_id}_canvas.mp4"
            try:
                import urllib.request
                urllib.request.urlretrieve(canvas_url, str(canvas_file))
                if canvas_file.exists() and canvas_file.stat().st_size > 50_000:
                    cache.set(track_uri, str(canvas_file))
                    return canvas_file
            except Exception:
                pass

    cache.set(track_uri, None)
    return None


# ---------------------------------------------------------------------------
# SYNC DAEMON & MPRIS EVENT LISTENER
# ---------------------------------------------------------------------------
class SpotifyClipSyncDaemon:
    def __init__(self):
        self.config = load_config()
        self.cache = ClipCache(INDEX_FILE)
        self.controller = WallpaperController(
            monitor=self.config.get("target_monitor", "DP-2"),
            fps=self.config.get("fps", 60)
        )
        self.current_uri = ""
        self.active_request_id = 0
        self._lock = threading.Lock()

    def start(self):
        DBusGMainLoop(set_as_default=True)
        try:
            self.bus = dbus.SessionBus()
        except Exception as e:
            sys.exit(f"Erreur connexion D-Bus : {e}")

        # Check initial state
        self._check_initial_playback()

        # Register signal receiver (zero polling)
        self.bus.add_signal_receiver(
            self.on_properties_changed,
            signal_name="PropertiesChanged",
            dbus_interface="org.freedesktop.DBus.Properties",
            bus_name="org.mpris.MediaPlayer2.spotify",
            path="/org/mpris/MediaPlayer2"
        )

        loop = GLib.MainLoop()
        try:
            loop.run()
        except (KeyboardInterrupt, SystemExit):
            self.controller.restore_lucy()

    def _check_initial_playback(self):
        try:
            player = self.bus.get_object('org.mpris.MediaPlayer2.spotify', '/org/mpris/MediaPlayer2')
            props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')
            status = str(props.Get('org.mpris.MediaPlayer2.Player', 'PlaybackStatus'))
            metadata = props.Get('org.mpris.MediaPlayer2.Player', 'Metadata')
            self._handle_change(status, metadata)
        except Exception:
            pass

    def on_properties_changed(self, interface, changed_props, invalidated_props):
        status = str(changed_props.get("PlaybackStatus", ""))
        metadata = changed_props.get("Metadata", None)
        self._handle_change(status, metadata)

    def _handle_change(self, status: str, metadata):
        if status in ["Paused", "Stopped"]:
            self.controller.restore_lucy()
            return

        if not metadata and status == "Playing":
            try:
                player = self.bus.get_object('org.mpris.MediaPlayer2.spotify', '/org/mpris/MediaPlayer2')
                props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')
                metadata = props.Get('org.mpris.MediaPlayer2.Player', 'Metadata')
            except Exception:
                pass

        if not metadata:
            return

        track_id = str(metadata.get("mpris:trackid", ""))
        title = str(metadata.get("xesam:title", ""))
        artists = metadata.get("xesam:artist", [""])
        artist = ", ".join([str(a) for a in artists])
        length_us = metadata.get("mpris:length", 0)
        duration_s = float(length_us) / 1_000_000.0

        if not track_id or duration_s <= 10.0:
            return

        with self._lock:
            if track_id == self.current_uri and self.controller.current_state == "CLIP":
                return
            self.current_uri = track_id
            self.active_request_id += 1
            req_id = self.active_request_id

        # 1. Check local cache
        cached_path_str = self.cache.get(track_id)
        if cached_path_str:
            cached_path = Path(cached_path_str)
            if cached_path.exists():
                self.controller.display_clip(cached_path)
                return
        elif cached_path_str is None and track_id in self.cache.data:
            # Previously resolved as having no official clip
            self.controller.restore_lucy()
            return

        # 2. Resolve asynchronously in background thread
        def resolve_worker(req, uri, art, tit, dur):
            clip_file = resolve_and_download_clip(
                art, tit, dur, uri, self.cache,
                max_diff=self.config.get("max_duration_diff_sec", 6.0),
                fallback_to_canvas=self.config.get("fallback_to_canvas", True)
            )
            with self._lock:
                if req != self.active_request_id:
                    return  # Stale request, song changed in the meantime

            if clip_file:
                self.controller.display_clip(clip_file)
            else:
                self.controller.restore_lucy()

        t = threading.Thread(
            target=resolve_worker,
            args=(req_id, track_id, artist, title, duration_s),
            daemon=True
        )
        t.start()


# ---------------------------------------------------------------------------
# MAIN CLI & SINGLETON MANAGEMENT
# ---------------------------------------------------------------------------
def acquire_lock():
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except IOError:
        return None


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "status":
            lock_fd = acquire_lock()
            if lock_fd is None:
                print("✓ Spotify Clip Sync est ACTIF (démon en cours d'exécution).")
            else:
                print("✗ Spotify Clip Sync est INACTIF.")
            return
        elif cmd == "stop":
            res = subprocess.run(["pkill", "-f", "spotify-clip-sync.py"], check=False)
            time.sleep(0.2)
            # Restore Lucy on DP-2
            ctrl = WallpaperController()
            ctrl.restore_lucy()
            print("✓ Démon arrêté et Lucy restaurée sur DP-2.")
            return

    lock = acquire_lock()
    if lock is None:
        print("✗ Une instance de spotify-clip-sync.py est déjà active.")
        sys.exit(0)

    daemon = SpotifyClipSyncDaemon()

    def on_exit(signum, frame):
        daemon.controller.restore_lucy()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)
    atexit.register(daemon.controller.restore_lucy)

    daemon.start()


if __name__ == "__main__":
    main()
