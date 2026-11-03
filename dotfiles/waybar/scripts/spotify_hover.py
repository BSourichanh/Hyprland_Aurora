#!/usr/bin/env python3
"""
Hover Monitor, Cover Art Cache & CSS Theme for Spotify Card.
Handles adaptive cursor coordinate tracking, background cover fetching,
and Aurora glassmorphism stylesheet definition.

Design Patterns:
- Observer / Poller: HoverMonitorThread adapts sampling rate based on cursor proximity.
- Service: CoverArtManager manages image resizing, rounded masking, and disk caching.
"""

import hashlib
import os
import threading
import time
import urllib.request
from typing import Callable, Optional

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk
from PIL import Image, ImageDraw

CACHE_DIR = "/tmp/spotify_card_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

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
        self.placeholder_path = os.path.join(cache_dir, "placeholder.png")
        self._ensure_placeholder()

    def _ensure_placeholder(self):
        if not os.path.exists(self.placeholder_path):
            img = Image.new("RGBA", (self.size, self.size), (20, 25, 45, 255))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([(0, 0), (self.size, self.size)], self.radius, fill=(20, 25, 45, 255))
            img.save(self.placeholder_path)

    def set_placeholder(self, gtk_image: Gtk.Image):
        gtk_image.set_from_file(self.placeholder_path)

    def load_cover_async(self, url: str, on_loaded: Callable[[str], None]):
        if not url:
            on_loaded(self.placeholder_path)
            return

        h = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{h}.png")
        if os.path.exists(cache_path):
            on_loaded(cache_path)
            return

        def fetch():
            raw_path = os.path.join(self.cache_dir, f"{h}_raw.jpg")
            try:
                urllib.request.urlretrieve(url, raw_path)
                im = Image.open(raw_path).resize((self.size, self.size), Image.Resampling.LANCZOS)
                mask = Image.new("L", (self.size, self.size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle([(0, 0), (self.size, self.size)], self.radius, fill=255)
                im_rounded = im.convert("RGBA")
                im_rounded.putalpha(mask)
                im_rounded.save(cache_path)
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


class HoverMonitorThread(threading.Thread):
    """Monitors cursor coordinates with adaptive tick rates to optimize CPU usage."""

    def __init__(self, window, hypr):
        super().__init__(daemon=True)
        self.window = window
        self.hypr = hypr

    def run(self):
        last_meta_check = 0.0
        while True:
            sleep_duration = 0.08
            try:
                if not self.window.is_card_visible and not self.window.player.is_running():
                    time.sleep(1.0)
                    continue

                now = time.time()
                if self.window.is_card_visible and (now - last_meta_check > 0.5):
                    last_meta_check = now
                    GLib.idle_add(self.window.update_metadata)

                x, y = self.hypr.get_cursor_position()
                if x is not None and y is not None:
                    if self.window.is_card_visible or y <= 80:
                        sleep_duration = 0.05
                    elif y > 200:
                        sleep_duration = 0.12

                    in_bar_dp2 = (630 <= x <= 890) and (0 <= y <= 44)
                    in_bar_dp1 = (2550 <= x <= 2810) and (0 <= y <= 44)
                    in_card_dp2 = (580 <= x <= 980) and (0 <= y <= 210)
                    in_card_dp1 = (2500 <= x <= 2900) and (0 <= y <= 210)

                    if not self.window.is_card_visible:
                        if in_bar_dp2:
                            GLib.idle_add(self.window.show_at, 600, 44)
                        elif in_bar_dp1:
                            GLib.idle_add(self.window.show_at, 2520, 44)
                    else:
                        in_zone = (
                            (self.window.active_monitor == 0 and in_card_dp2) or
                            (self.window.active_monitor == 1 and in_card_dp1)
                        )
                        if in_zone:
                            if self.window.hide_timer:
                                GLib.idle_add(self.window.cancel_hide_timer)
                        else:
                            if not self.window.hide_timer:
                                GLib.idle_add(self.window.schedule_hide_check)
            except Exception:
                sleep_duration = 0.5
            time.sleep(sleep_duration)
