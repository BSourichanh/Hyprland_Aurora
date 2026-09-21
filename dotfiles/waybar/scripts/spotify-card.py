#!/usr/bin/env python3
"""
Spotify Floating Card Daemon & IPC Controller for Hyprland / Waybar
Displays a glassmorphism floating popup with cover art, track info,
and like/hide controls when hovering or clicking the Waybar mini-player.

Architectural Design Patterns:
- Repository Pattern: TrackRepository for atomic and thread-safe persistence.
- Facade / Adapter Pattern: MPRISPlayerFacade for native D-Bus media calls.
- Service / Singleton Pattern: HyprlandIPCService for compositor interaction.
- Command Pattern: IPCCommandHandler for IPC UNIX socket dispatching.
- Observer Pattern: MPRISObserver for reactive song changes via D-Bus.
- View Component: SpotifyCardWindow for GTK3 UI rendering.
"""

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Set, Tuple

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GLib, Gtk, Pango
from PIL import Image, ImageDraw

# Initialize D-Bus GLib main loop integration
DBusGMainLoop(set_as_default=True)

# Configuration Constants
CACHE_DIR = "/tmp/spotify_card_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
LIKES_FILE = os.path.expanduser("~/.config/spotify_likes.json")
HIDDEN_FILE = os.path.expanduser("~/.config/spotify_hidden.json")
COMMAND_SOCK = "/tmp/spotify_card.sock"
LOCK_FILE = "/tmp/spotify_card.lock"
SSE_PORT = 8975


# ============================================================================
# DATA TRANSFER OBJECTS (DTO)
# ============================================================================

@dataclass(frozen=True)
class TrackMetadata:
    """Immutable data transfer object representing current track info."""
    title: str = "Titre inconnu"
    artist: str = "Artiste inconnu"
    album: str = "Album inconnu"
    art_url: str = ""
    uri: str = ""
    is_valid: bool = False


# ============================================================================
# REPOSITORY PATTERN: PERSISTENCE (LIKES & HIDDEN TRACKS)
# ============================================================================

class TrackRepository:
    """Thread-safe and atomic repository for user preferences."""

    def __init__(self, likes_path: str = LIKES_FILE, hidden_path: str = HIDDEN_FILE):
        self._likes_path = likes_path
        self._hidden_path = hidden_path
        self._lock = threading.Lock()
        self._likes: Set[str] = self._load_set(self._likes_path)
        self._hidden: Set[str] = self._load_set(self._hidden_path)

    @staticmethod
    def _load_set(path: str) -> Set[str]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    @staticmethod
    def _atomic_save(path: str, data: Set[str]):
        """Atomic write via temporary file replacement to prevent data corruption."""
        dir_name = os.path.dirname(path) or "."
        try:
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                json.dump(list(data), tf)
                temp_name = tf.name
            os.replace(temp_name, path)
        except Exception:
            if 'temp_name' in locals() and os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except OSError:
                    pass

    def is_liked(self, uri: str) -> bool:
        with self._lock:
            return uri in self._likes

    def is_hidden(self, uri: str) -> bool:
        with self._lock:
            return uri in self._hidden

    def set_liked(self, uri: str, liked: bool):
        with self._lock:
            if liked:
                self._likes.add(uri)
            else:
                self._likes.discard(uri)
            self._atomic_save(self._likes_path, self._likes)

    def toggle_like(self, uri: str) -> bool:
        with self._lock:
            if uri in self._likes:
                self._likes.discard(uri)
                status = False
            else:
                self._likes.add(uri)
                status = True
            self._atomic_save(self._likes_path, self._likes)
            return status

    def hide_track(self, uri: str):
        with self._lock:
            self._hidden.add(uri)
            self._atomic_save(self._hidden_path, self._hidden)


# ============================================================================
# FACADE PATTERN: MPRIS PLAYER CONTROLLER
# ============================================================================

class MPRISPlayerFacade:
    """Facade encapsulating all MPRIS D-Bus interactions without shell forks."""

    def __init__(self):
        self._session_bus: Optional[dbus.SessionBus] = None

    def get_bus(self) -> dbus.SessionBus:
        if self._session_bus is None:
            self._session_bus = dbus.SessionBus()
        return self._session_bus

    def _get_player_interface(self):
        bus = self.get_bus()
        player = bus.get_object("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2", introspect=False)
        return dbus.Interface(player, "org.mpris.MediaPlayer2.Player")

    def _get_props_interface(self):
        bus = self.get_bus()
        player = bus.get_object("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2", introspect=False)
        return dbus.Interface(player, "org.freedesktop.DBus.Properties")

    def is_running(self) -> bool:
        try:
            props = self._get_props_interface()
            status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus", timeout=0.08))
            return status in ["Playing", "Paused"]
        except Exception:
            return False

    def get_metadata(self) -> TrackMetadata:
        try:
            props = self._get_props_interface()
            meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata", timeout=0.08)
            title = str(meta.get("xesam:title", "Titre inconnu"))
            artists = meta.get("xesam:artist", ["Artiste inconnu"])
            artist = ", ".join([str(a) for a in artists])
            album = str(meta.get("xesam:album", "Album inconnu"))
            art_url = str(meta.get("mpris:artUrl", ""))
            uri = str(meta.get("xesam:url", "") or meta.get("mpris:trackid", ""))
            return TrackMetadata(
                title=title,
                artist=artist,
                album=album,
                art_url=art_url,
                uri=uri,
                is_valid=True
            )
        except Exception:
            return TrackMetadata(is_valid=False)

    def next(self):
        """Native D-Bus next call; eliminates playerctl fork."""
        try:
            player = self._get_player_interface()
            player.Next(timeout=0.2)
        except Exception:
            pass

    def previous(self):
        """Native D-Bus previous call."""
        try:
            player = self._get_player_interface()
            player.Previous(timeout=0.2)
        except Exception:
            pass

    def play_pause(self):
        """Native D-Bus play-pause toggle."""
        try:
            player = self._get_player_interface()
            player.PlayPause(timeout=0.2)
        except Exception:
            pass


# ============================================================================
# SERVICE PATTERN: HYPRLAND IPC
# ============================================================================

class HyprlandIPCService:
    """Service handling Hyprland UNIX socket IPC queries and dispatches."""

    def __init__(self):
        self._cached_sock: Optional[str] = None

    def get_socket_path(self) -> Optional[str]:
        if self._cached_sock and os.path.exists(self._cached_sock):
            return self._cached_sock

        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        if sig:
            sock = f"{xdg}/hypr/{sig}/.socket.sock"
            if os.path.exists(sock):
                self._cached_sock = sock
                return sock
        return None

    def get_cursor_position(self) -> Tuple[Optional[int], Optional[int]]:
        sock_path = self.get_socket_path()
        if not sock_path:
            return None, None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.04)
                s.connect(sock_path)
                s.sendall(b"cursorpos")
                res = s.recv(1024).decode().strip()
                parts = res.split(",")
                return int(parts[0].strip()), int(parts[1].strip())
        except Exception:
            return None, None

    def move_window_pixel(self, x: int, y: int, window_class: str = "spotify-card"):
        sock_path = self.get_socket_path()
        if not sock_path:
            return
        cmd = f"dispatch movewindowpixel exact {x} {y},class:{window_class}"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.05)
                s.connect(sock_path)
                s.sendall(cmd.encode())
                s.recv(1024)
        except Exception:
            pass


# ============================================================================
# SSE EVENT BROADCASTER & SPICETIFY BRIDGE
# ============================================================================

class SSENotifier:
    """Manages active Server-Sent Events subscribers."""

    def __init__(self):
        self._clients = []
        self._lock = threading.Lock()

    def add_client(self, wfile):
        with self._lock:
            self._clients.append(wfile)

    def remove_client(self, wfile):
        with self._lock:
            if wfile in self._clients:
                self._clients.remove(wfile)

    def has_clients(self) -> bool:
        with self._lock:
            return len(self._clients) > 0

    def broadcast(self, action: str, **extra):
        payload = {"action": action, **extra}
        msg = f"data: {json.dumps(payload)}\n\n".encode()
        with self._lock:
            active = list(self._clients)
        for w in active:
            try:
                w.write(msg)
                w.flush()
            except Exception:
                self.remove_client(w)


class BridgeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP & SSE bridge connecting Spicetify extensions to the desktop daemon."""
    notifier: Optional[SSENotifier] = None
    repo: Optional[TrackRepository] = None
    on_track_update = None
    on_like_update = None

    def log_message(self, format, *args):
        return  # Silent logging

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if self.notifier:
                self.notifier.add_client(self.wfile)
            try:
                while True:
                    time.sleep(1)
            except Exception:
                if self.notifier:
                    self.notifier.remove_client(self.wfile)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/status":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode()
            try:
                data = json.loads(body)
                uri = data.get("uri")
                liked = data.get("liked", False)
                if uri and self.repo:
                    self.repo.set_liked(uri, liked)
                    if self.on_like_update:
                        self.on_like_update(uri, liked)
            except Exception:
                pass
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif self.path == "/songchange":
            if self.on_track_update:
                self.on_track_update()
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ============================================================================
# GTK VIEW COMPONENT: SPOTIFY CARD WINDOW
# ============================================================================

class SpotifyCardWindow(Gtk.Window):
    """GTK3 Glassmorphism Floating Window adhering to Hybrid Summer Theme."""

    def __init__(self, repo: TrackRepository, player: MPRISPlayerFacade,
                 hypr: HyprlandIPCService, notifier: SSENotifier):
        GLib.set_prgname("spotify-card")
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("spotify-card")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self.repo = repo
        self.player = player
        self.hypr = hypr
        self.notifier = notifier

        self.current_uri = ""
        self.current_title = ""
        self.loaded_cover_url = None
        self.is_liked = False
        self.is_card_visible = False
        self.active_monitor = 0
        self.hide_timer = None

        self._apply_theme_css()
        self._build_ui()

        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)

    def _apply_theme_css(self):
        css = b"""
        window {
            background-color: transparent;
        }
        .card-container {
            border: 2px solid transparent;
            border-radius: 17px;
            background-image: linear-gradient(rgba(10, 15, 30, 0.85), rgba(10, 15, 30, 0.85)), 
                              linear-gradient(135deg, #00f0ff, #7aa2f7, #9778d0);
            background-origin: border-box;
            background-clip: padding-box, border-box;
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
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.main_box.get_style_context().add_class("card-container")

        self.img_cover = Gtk.Image()
        self._set_placeholder_cover()
        self.main_box.pack_start(self.img_cover, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.main_box.pack_start(vbox, True, True, 0)

        badge = Gtk.Label()
        badge.set_markup(
            "<span font_family='FontAwesome' color='#00f0ff'></span> "
            "<span color='#00f0ff' font='9' weight='bold'>SPOTIFY</span>"
        )
        badge.set_xalign(0)
        vbox.pack_start(badge, False, False, 0)

        self.lbl_title = Gtk.Label()
        self.lbl_title.set_markup("<span color='#ffffff' font='11' weight='bold'>En attente…</span>")
        self.lbl_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_title.set_max_width_chars(21)
        self.lbl_title.set_xalign(0)
        vbox.pack_start(self.lbl_title, False, False, 0)

        self.lbl_artist = Gtk.Label()
        self.lbl_artist.set_markup("<span color='#00f0ff' font='10'>Artiste</span>")
        self.lbl_artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_artist.set_max_width_chars(23)
        self.lbl_artist.set_xalign(0)
        vbox.pack_start(self.lbl_artist, False, False, 0)

        self.lbl_album = Gtk.Label()
        self.lbl_album.set_markup("<span color='#94a3b8' font='9'>Album</span>")
        self.lbl_album.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_album.set_max_width_chars(25)
        self.lbl_album.set_xalign(0)
        vbox.pack_start(self.lbl_album, False, False, 0)

        vbox.pack_start(Gtk.Box(), True, True, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.btn_like = Gtk.Button()
        self.lbl_btn_like = Gtk.Label()
        self.lbl_btn_like.set_markup("<span font_family='FontAwesome' color='#f43f5e'></span>  Liker")
        self.btn_like.add(self.lbl_btn_like)
        self.btn_like.get_style_context().add_class("btn-like")
        self.btn_like.connect("clicked", self._on_like_clicked)

        self.btn_hide = Gtk.Button()
        self.lbl_btn_hide = Gtk.Label()
        self.lbl_btn_hide.set_markup("<span font_family='FontAwesome' color='#cbd5e1'></span>  Masquer")
        self.btn_hide.add(self.lbl_btn_hide)
        self.btn_hide.get_style_context().add_class("btn-hide")
        self.btn_hide.connect("clicked", self._on_hide_clicked)

        btn_box.pack_start(self.btn_like, False, False, 0)
        btn_box.pack_start(self.btn_hide, False, False, 0)
        vbox.pack_start(btn_box, False, False, 0)

        self.add(self.main_box)

    def _set_placeholder_cover(self):
        cache_path = os.path.join(CACHE_DIR, "placeholder.png")
        if not os.path.exists(cache_path):
            img = Image.new("RGBA", (128, 128), (20, 25, 45, 255))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([(0, 0), (128, 128)], 14, fill=(20, 25, 45, 255))
            img.save(cache_path)
        self.img_cover.set_from_file(cache_path)
        self.loaded_cover_url = None

    def _update_cover(self, url: str):
        if not url:
            self._set_placeholder_cover()
            return
        if url == self.loaded_cover_url:
            return

        h = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(CACHE_DIR, f"{h}.png")
        if os.path.exists(cache_path):
            self.img_cover.set_from_file(cache_path)
            self.loaded_cover_url = url
            return

        def fetch():
            raw_path = os.path.join(CACHE_DIR, f"{h}_raw.jpg")
            try:
                urllib.request.urlretrieve(url, raw_path)
                im = Image.open(raw_path).resize((128, 128), Image.Resampling.LANCZOS)
                mask = Image.new("L", (128, 128), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle([(0, 0), (128, 128)], 14, fill=255)
                im_rounded = im.convert("RGBA")
                im_rounded.putalpha(mask)
                im_rounded.save(cache_path)

                def apply():
                    self.img_cover.set_from_file(cache_path)
                    self.loaded_cover_url = url
                GLib.idle_add(apply)
            except Exception:
                pass
            finally:
                if os.path.exists(raw_path):
                    try:
                        os.remove(raw_path)
                    except OSError:
                        pass

        threading.Thread(target=fetch, daemon=True).start()

    def update_metadata(self):
        meta = self.player.get_metadata()
        if not meta.is_valid:
            self.lbl_title.set_markup("<span color='#94a3b8' font='10'>Spotify arrêté</span>")
            self.lbl_artist.set_markup("")
            self.lbl_album.set_markup("")
            self._set_placeholder_cover()
            return

        self.current_uri = meta.uri
        self.current_title = meta.title

        safe_title = GLib.markup_escape_text(meta.title)
        safe_artist = GLib.markup_escape_text(meta.artist)
        safe_album = GLib.markup_escape_text(meta.album)

        self.lbl_title.set_markup(f"<span color='#ffffff' font='11' weight='bold'>{safe_title}</span>")
        self.lbl_artist.set_markup(f"<span color='#00f0ff' font='10'>{safe_artist}</span>")
        self.lbl_album.set_markup(f"<span color='#94a3b8' font='9'>{safe_album}</span>")

        self._update_cover(meta.art_url)
        self.update_like_status(self.repo.is_liked(meta.uri))

        if self.repo.is_hidden(meta.uri):
            self.player.next()

    def update_like_status(self, liked: bool):
        self.is_liked = liked
        ctx = self.btn_like.get_style_context()
        if liked:
            ctx.remove_class("btn-like")
            ctx.add_class("btn-liked")
            self.lbl_btn_like.set_markup("<span font_family='FontAwesome' color='#ffffff'></span>  Liké")
        else:
            ctx.remove_class("btn-liked")
            ctx.add_class("btn-like")
            self.lbl_btn_like.set_markup("<span font_family='FontAwesome' color='#f43f5e'></span>  Liker")

    def _on_like_clicked(self, _widget=None):
        if self.current_uri:
            self.is_liked = self.repo.toggle_like(self.current_uri)
            self.update_like_status(self.is_liked)
            self.notifier.broadcast("like")

    def _on_hide_clicked(self, _widget=None):
        if self.current_uri:
            self.repo.hide_track(self.current_uri)
            self.notifier.broadcast("hide", uri=self.current_uri)
            self.player.next()
            self.lbl_btn_hide.set_markup("<span font_family='FontAwesome' color='#f87171'></span>  Masqué !")
            GLib.timeout_add(700, lambda: self.lbl_btn_hide.set_markup(
                "<span font_family='FontAwesome' color='#cbd5e1'></span>  Masquer"
            ))
            GLib.timeout_add(300, self.update_metadata)

    def cancel_hide_timer(self):
        if self.hide_timer:
            GLib.source_remove(self.hide_timer)
            self.hide_timer = None

    def show_at(self, target_x: int, target_y: int):
        if not self.player.is_running():
            return
        self.cancel_hide_timer()
        self.active_monitor = 1 if target_x >= 1920 else 0
        self.update_metadata()
        self.show_all()
        self.is_card_visible = True

        def move():
            self.hypr.move_window_pixel(target_x, target_y, "spotify-card")
        GLib.idle_add(move)
        GLib.timeout_add(20, move)

    def hide_card(self):
        self.cancel_hide_timer()
        self.hide()
        self.is_card_visible = False

    def _on_enter(self, _widget, _event):
        self.cancel_hide_timer()

    def _on_leave(self, _widget, _event):
        self.schedule_hide_check()

    def schedule_hide_check(self):
        self.cancel_hide_timer()
        self.hide_timer = GLib.timeout_add(350, self._check_and_hide)

    def _check_and_hide(self):
        self.hide_timer = None
        x, y = self.hypr.get_cursor_position()
        if x is not None and y is not None:
            if self.active_monitor == 0:
                in_active_zone = (580 <= x <= 980) and (0 <= y <= 210)
            else:
                in_active_zone = (2500 <= x <= 2900) and (0 <= y <= 210)
            if in_active_zone:
                return False
        self.hide_card()
        return False


# ============================================================================
# CONTROLLER: HOVER & ADAPTIVE POLLING
# ============================================================================

class HoverMonitorThread(threading.Thread):
    """Monitors cursor coordinates with adaptive tick rates to optimize CPU usage."""

    def __init__(self, window: SpotifyCardWindow, hypr: HyprlandIPCService):
        super().__init__(daemon=True)
        self.window = window
        self.hypr = hypr

    def run(self):
        last_meta_check = 0.0
        while True:
            sleep_duration = 0.08
            try:
                now = time.time()
                if self.window.is_card_visible and (now - last_meta_check > 0.5):
                    last_meta_check = now
                    GLib.idle_add(self.window.update_metadata)

                x, y = self.hypr.get_cursor_position()
                if x is not None and y is not None:
                    # Adaptive rate: fast near active zones, relaxed elsewhere
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
                            self.window.is_card_visible = True
                            GLib.idle_add(self.window.show_at, 600, 44)
                        elif in_bar_dp1:
                            self.window.is_card_visible = True
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


# ============================================================================
# COMMAND PATTERN: UNIX IPC SOCKET SERVER
# ============================================================================

class IPCCommandHandler:
    """Dispatches incoming IPC socket commands to window actions."""

    def __init__(self, window: SpotifyCardWindow, hypr: HyprlandIPCService):
        self.window = window
        self.hypr = hypr
        self._commands = {
            "toggle": self._cmd_toggle,
            "show": self._cmd_show,
            "hide": self._cmd_hide,
            "like": self._cmd_like,
            "masquer": self._cmd_masquer,
        }

    def handle(self, cmd_name: str):
        action = self._commands.get(cmd_name)
        if action:
            action()

    def _cmd_toggle(self):
        if self.window.is_card_visible:
            GLib.idle_add(self.window.hide_card)
        else:
            self._cmd_show()

    def _cmd_show(self):
        self.window.is_card_visible = True
        x, _ = self.hypr.get_cursor_position()
        target_x = 2520 if (x and x >= 1920) else 600
        GLib.idle_add(self.window.show_at, target_x, 44)

    def _cmd_hide(self):
        GLib.idle_add(self.window.hide_card)

    def _cmd_like(self):
        GLib.idle_add(self.window._on_like_clicked, None)

    def _cmd_masquer(self):
        GLib.idle_add(self.window._on_hide_clicked, None)


class CommandSocketThread(threading.Thread):
    """UNIX Domain Socket listener for desktop actions."""

    def __init__(self, handler: IPCCommandHandler):
        super().__init__(daemon=True)
        self.handler = handler

    def run(self):
        if os.path.exists(COMMAND_SOCK):
            try:
                os.remove(COMMAND_SOCK)
            except Exception:
                pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(COMMAND_SOCK)
        server.listen(5)
        while True:
            try:
                conn, _ = server.accept()
                data = conn.recv(1024).decode().strip()
                conn.sendall(b"OK\n")
                conn.close()
                self.handler.handle(data)
            except Exception:
                pass


# ============================================================================
# OBSERVER PATTERN: MPRIS DBUS SIGNALS
# ============================================================================

def setup_mpris_observer(window: SpotifyCardWindow, player: MPRISPlayerFacade):
    """Subscribes to D-Bus PropertiesChanged events to notify the view immediately."""
    def on_properties_changed(interface_name, changed_properties, _invalidated):
        if interface_name == "org.mpris.MediaPlayer2.Player":
            if "Metadata" in changed_properties:
                if window.is_card_visible:
                    GLib.idle_add(window.update_metadata)

    try:
        bus = player.get_bus()
        bus.add_signal_receiver(
            on_properties_changed,
            signal_name="PropertiesChanged",
            dbus_interface="org.freedesktop.DBus.Properties",
            path="/org/mpris/MediaPlayer2"
        )
    except Exception:
        pass


# ============================================================================
# APPLICATION ENTRYPOINT & SINGLETON BOOTSTRAP
# ============================================================================

_lock_fd = None

def acquire_singleton_lock() -> bool:
    global _lock_fd
    try:
        _lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, BlockingIOError):
        return False


def send_client_cmd(cmd: str) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(COMMAND_SOCK)
            s.sendall(cmd.encode())
            s.recv(1024)
            return True
    except Exception:
        return False


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "toggle"

    if arg in ["toggle", "show", "hide", "like", "masquer"]:
        if send_client_cmd(arg):
            sys.exit(0)
        # Daemon starting or not ready: retry before bootstrapping
        if not acquire_singleton_lock():
            for _ in range(10):
                time.sleep(0.1)
                if send_client_cmd(arg):
                    sys.exit(0)
            sys.exit(0)
    else:
        if not acquire_singleton_lock():
            print("spotify-card: déjà en cours d'exécution.")
            sys.exit(0)

    # Instantiate Core Services
    repo = TrackRepository()
    player = MPRISPlayerFacade()
    hypr = HyprlandIPCService()
    notifier = SSENotifier()

    # Configure HTTP SSE Bridge
    BridgeHTTPHandler.notifier = notifier
    BridgeHTTPHandler.repo = repo

    window = SpotifyCardWindow(repo, player, hypr, notifier)

    def on_sse_track_update():
        if window.is_card_visible:
            GLib.idle_add(window.update_metadata)

    def on_sse_like_update(uri: str, liked: bool):
        if window.is_card_visible:
            if window.current_uri != uri:
                GLib.idle_add(window.update_metadata)
            else:
                GLib.idle_add(window.update_like_status, liked)

    BridgeHTTPHandler.on_track_update = on_sse_track_update
    BridgeHTTPHandler.on_like_update = on_sse_like_update

    # Setup MPRIS Observer
    setup_mpris_observer(window, player)

    # Launch Background Threads
    def run_http():
        try:
            server = HTTPServer(("127.0.0.1", SSE_PORT), BridgeHTTPHandler)
            server.serve_forever()
        except Exception:
            pass

    threading.Thread(target=run_http, daemon=True).start()
    HoverMonitorThread(window, hypr).start()

    cmd_handler = IPCCommandHandler(window, hypr)
    CommandSocketThread(cmd_handler).start()

    if arg in ["toggle", "show"]:
        cmd_handler.handle("show")

    Gtk.main()


if __name__ == "__main__":
    main()

