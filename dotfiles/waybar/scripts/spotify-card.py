#!/usr/bin/env python3
"""
Spotify Floating Card Daemon & IPC Controller for Hyprland / Waybar
Displays a glassmorphism floating popup with cover art, track info,
and like/hide controls when hovering or clicking the Waybar mini-player.

Architectural Design Patterns:
- View Component: SpotifyCardWindow for GTK3 UI rendering (Glassmorphism Aurora).
- Service Integration: Coordinates MPRISPlayerFacade, HyprlandIPCService & SSENotifier.
"""

import os
from pathlib import Path
import sys
import time

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

from spotify_mpris import (
    TrackMetadata,
    TrackRepository,
    MPRISPlayerFacade,
    setup_mpris_observer,
)
from spotify_server import SSENotifier, start_sse_server, SSE_PORT
from spotify_ipc import (
    HyprlandIPCService,
    IPCCommandHandler,
    CommandSocketThread,
    acquire_singleton_lock,
    send_client_cmd,
)
from spotify_hover import HoverMonitorThread, CoverArtManager, AURORA_CARD_CSS


class SpotifyCardWindow(Gtk.Window):
    """GTK3 Glassmorphism Floating Window adhering to Aurora Theme."""

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
        self.cover_mgr = CoverArtManager()

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
        provider = Gtk.CssProvider()
        provider.load_from_data(AURORA_CARD_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.main_box.get_style_context().add_class("card-container")

        self.img_cover = Gtk.Image()
        self.cover_mgr.set_placeholder(self.img_cover)
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

    def _on_cover_loaded(self, path: str):
        self.img_cover.set_from_file(path)

    def update_metadata(self):
        meta = self.player.get_metadata()
        if not meta.is_valid:
            self.lbl_title.set_markup("<span color='#94a3b8' font='10'>Spotify arrêté</span>")
            self.lbl_artist.set_markup("")
            self.lbl_album.set_markup("")
            self.cover_mgr.set_placeholder(self.img_cover)
            self.loaded_cover_url = None
            return

        self.current_uri = meta.uri
        self.current_title = meta.title

        safe_title = GLib.markup_escape_text(meta.title)
        safe_artist = GLib.markup_escape_text(meta.artist)
        safe_album = GLib.markup_escape_text(meta.album)

        self.lbl_title.set_markup(f"<span color='#ffffff' font='11' weight='bold'>{safe_title}</span>")
        self.lbl_artist.set_markup(f"<span color='#00f0ff' font='10'>{safe_artist}</span>")
        self.lbl_album.set_markup(f"<span color='#94a3b8' font='9'>{safe_album}</span>")

        if meta.art_url != self.loaded_cover_url:
            self.loaded_cover_url = meta.art_url
            self.cover_mgr.load_cover_async(meta.art_url, self._on_cover_loaded)

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


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "toggle"

    if arg in ["toggle", "show", "hide", "like", "masquer"]:
        if send_client_cmd(arg):
            sys.exit(0)
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

    # Core Services Initialization
    repo = TrackRepository()
    player = MPRISPlayerFacade()
    hypr = HyprlandIPCService()
    notifier = SSENotifier()

    window = SpotifyCardWindow(repo, player, hypr, notifier)

    # SSE Event Callbacks
    def on_sse_track():
        if window.is_card_visible:
            GLib.idle_add(window.update_metadata)

    def on_sse_like(uri: str, liked: bool):
        if window.is_card_visible:
            if window.current_uri != uri:
                GLib.idle_add(window.update_metadata)
            else:
                GLib.idle_add(window.update_like_status, liked)

    # Start SSE / HTTP Bridge Server
    start_sse_server(
        port=SSE_PORT,
        notifier=notifier,
        repo=repo,
        on_track_update=on_sse_track,
        on_like_update=on_sse_like
    )

    # MPRIS Observer
    setup_mpris_observer(
        on_metadata_changed=lambda: GLib.idle_add(window.update_metadata) if window.is_card_visible else None,
        player=player
    )

    # Background Threads
    HoverMonitorThread(window, hypr).start()

    cmd_handler = IPCCommandHandler({
        "toggle": lambda: GLib.idle_add(window.hide_card) if window.is_card_visible else cmd_handler.handle("show"),
        "show": lambda: GLib.idle_add(
            window.show_at,
            2520 if (hypr.get_cursor_position()[0] and hypr.get_cursor_position()[0] >= 1920) else 600,
            44
        ),
        "hide": lambda: GLib.idle_add(window.hide_card),
        "like": lambda: GLib.idle_add(window._on_like_clicked, None),
        "masquer": lambda: GLib.idle_add(window._on_hide_clicked, None),
    })
    CommandSocketThread(cmd_handler).start()

    if arg in ["toggle", "show"]:
        cmd_handler.handle("show")

    Gtk.main()


if __name__ == "__main__":
    main()
