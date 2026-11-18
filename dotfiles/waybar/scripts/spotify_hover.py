#!/usr/bin/env python3
"""
Hover Monitor, Cover Art Cache & CSS Theme for Spotify Card.
Handles adaptive cursor tracking across dynamic monitor geometries, lock checks,
safe bounded cover caching, and Aurora glassmorphism stylesheet definition.
"""

import hashlib
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
HYPR_SCRIPTS_DIR = SCRIPT_DIR.parent.parent / "hypr" / "scripts"
for p in (SCRIPT_DIR, HYPR_SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from hypr_ipc import get_aurora_runtime_dir, is_session_locked

CACHE_DIR = str(get_aurora_runtime_dir() / "spotify_covers")
os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
MAX_CACHE_FILES = 64
MAX_COVER_BYTES = 10 * 1024 * 1024

AURORA_CARD_CSS = b"""
window {
    background-color: transparent;
}
.card-container {
    border: 2px solid rgba(0, 240, 255, 0.65);
    border-radius: 17px;
    background-color: rgba(10, 15, 30, 0.50);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45), 0 0 18px rgba(0, 240, 255, 0.20);
    padding: 14px;
}
.btn-like {
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.35);
    border-radius: 8px;
    padding: 5px 12px;
    color: #f43f5e;
    font-weight: 600;
}
.btn-like:hover {
    background: rgba(244, 63, 94, 0.25);
    border-color: rgba(244, 63, 94, 0.6);
}
.btn-liked {
    background: rgba(244, 63, 94, 0.35);
    border: 1px solid #f43f5e;
    border-radius: 8px;
    padding: 5px 12px;
    color: #ffffff;
    font-weight: 700;
}
.btn-liked:hover {
    background: rgba(244, 63, 94, 0.45);
}
.btn-hide {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 8px;
    padding: 5px 12px;
    color: #cbd5e1;
    font-weight: 600;
}
.btn-hide:hover {
    background: rgba(239, 68, 68, 0.25);
    color: #fca5a5;
    border-color: rgba(239, 68, 68, 0.45);
}
"""


class CoverArtManager:
    """Manages disk caching and rounded thumbnail generation for album covers."""

    def __init__(self, cache_dir: str = CACHE_DIR, size: int = 128, radius: int = 14):
        self.cache_dir = cache_dir
        self.size = size
        self.radius = radius
        os.makedirs(self.cache_dir, mode=0o700, exist_ok=True)
        self.placeholder_path = os.path.join(cache_dir, "placeholder.png")
        self._ensure_placeholder()

    def _ensure_placeholder(self):
        if not os.path.exists(self.placeholder_path):
            img = Image.new("RGBA", (self.size, self.size), (20, 25, 45, 255))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([(0, 0), (self.size, self.size)], self.radius, fill=(20, 25, 45, 255))
            img.save(self.placeholder_path)

    def _prune_cache(self):
        try:
            entries = [
                os.path.join(self.cache_dir, f)
                for f in os.listdir(self.cache_dir)
                if f.endswith(".png") and f != "placeholder.png"
            ]
            if len(entries) <= MAX_CACHE_FILES:
                return
            entries.sort(key=lambda p: os.path.getmtime(p))
            for victim in entries[: len(entries) - MAX_CACHE_FILES]:
                try:
                    os.remove(victim)
                except OSError:
                    pass
        except OSError:
            pass

    def set_placeholder(self, gtk_image: Gtk.Image):
        gtk_image.set_from_file(self.placeholder_path)

    def load_cover_async(self, url: str, on_loaded: Callable[[str], None]):
        if not url:
            on_loaded(self.placeholder_path)
            return

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https", "file"):
            on_loaded(self.placeholder_path)
            return

        h = hashlib.md5(url.encode("utf-8")).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{h}.png")
        if os.path.exists(cache_path):
            on_loaded(cache_path)
            return

        def fetch():
            raw_path = os.path.join(self.cache_dir, f"{h}_raw.img")
            try:
                if parsed.scheme == "file":
                    local_path = urllib.request.url2pathname(parsed.path)
                    shutil.copyfile(local_path, raw_path)
                else:
                    req = urllib.request.Request(url, headers={"User-Agent": "AuroraSpotifyCard/1.0"})
                    with urllib.request.urlopen(req, timeout=5.0) as resp, open(raw_path, "wb") as out:
                        total = 0
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > MAX_COVER_BYTES:
                                raise ValueError("Cover image exceeds size limit")
                            out.write(chunk)

                with Image.open(raw_path) as opened:
                    im = opened.resize((self.size, self.size), Image.Resampling.LANCZOS).convert("RGBA")
                mask = Image.new("L", (self.size, self.size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle([(0, 0), (self.size, self.size)], self.radius, fill=255)
                im.putalpha(mask)
                im.save(cache_path)
                self._prune_cache()
                GLib.idle_add(on_loaded, cache_path)
            except Exception:
                pass
            finally:
                if os.path.exists(raw_path):
                    try:
                        os.remove(raw_path)
                    except OSError:
                        pass

        threading.Thread(target=fetch, daemon=True).start()


def compute_hover_zones(mon_rect: tuple) -> tuple:
    """Computes (bar_zone, card_zone, target_origin) dynamically from monitor rect (mx, my, mw, mh)."""
    mx, my, mw, _ = mon_rect
    bar_x1 = mx + int(round(mw * 0.328))
    bar_x2 = mx + int(round(mw * 0.464))
    card_w = 465
    target_x = mx + max(10, min(mw - card_w - 10, int(round(mw * 0.3125))))
    target_y = my + 44
    bar_zone = (bar_x1, bar_x2, my, target_y)
    card_zone = (target_x - 20, target_x + 380, my, my + 210)
    return bar_zone, card_zone, (target_x, target_y)


class HoverMonitorThread(threading.Thread):
    """Monitors cursor coordinates without touching D-Bus from the worker thread."""

    def __init__(self, window, hypr):
        super().__init__(daemon=True)
        self.window = window
        self.hypr = hypr

    def run(self):
        last_meta_check = 0.0
        while True:
            sleep_duration = 0.08
            try:
                if is_session_locked():
                    if self.window.is_card_visible:
                        GLib.idle_add(self.window.hide_card)
                    time.sleep(0.5)
                    continue

                if not self.window.is_card_visible and not self.window.is_player_active:
                    time.sleep(1.0)
                    continue

                now = time.time()
                if self.window.is_card_visible and (now - last_meta_check > 0.5):
                    last_meta_check = now
                    GLib.idle_add(self.window.update_metadata)

                x, y = self.hypr.get_cursor_position()
                if x is not None and y is not None:
                    mon_rect = self.hypr.get_monitor_rect_at(x, y)
                    mx, my, _, _ = mon_rect
                    bar_zone, card_zone, (target_x, target_y) = compute_hover_zones(mon_rect)

                    rel_y = y - my
                    if self.window.is_card_visible or rel_y <= 80:
                        sleep_duration = 0.05
                    elif rel_y > 200:
                        sleep_duration = 0.12

                    in_bar = (bar_zone[0] <= x <= bar_zone[1]) and (bar_zone[2] <= y <= bar_zone[3])
                    if not self.window.is_card_visible:
                        if in_bar:
                            GLib.idle_add(self.window.show_at, target_x, target_y)
                    else:
                        active_rect = self.window.active_monitor_rect or mon_rect
                        _, active_card_zone, _ = compute_hover_zones(active_rect)
                        in_card = (
                            active_card_zone[0] <= x <= active_card_zone[1]
                            and active_card_zone[2] <= y <= active_card_zone[3]
                        )
                        if in_card:
                            if self.window.hide_timer:
                                GLib.idle_add(self.window.cancel_hide_timer)
                        elif not self.window.hide_timer:
                            GLib.idle_add(self.window.schedule_hide_check)
            except Exception:
                sleep_duration = 0.5
            time.sleep(sleep_duration)