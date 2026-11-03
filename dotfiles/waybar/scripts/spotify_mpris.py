#!/usr/bin/env python3
"""
MPRIS D-Bus Client & Preferences Repository for Spotify Card Daemon.
Encapsulates native D-Bus IPC calls, player controls, and atomic persistence.

Design Patterns:
- Repository Pattern: TrackRepository for thread-safe likes/hidden persistence.
- Facade Pattern: MPRISPlayerFacade for media controls via native D-Bus.
- Observer Pattern: setup_mpris_observer for reactive D-Bus signal dispatching.
"""

from dataclasses import dataclass
import json
import os
import subprocess
import tempfile
import threading
from typing import Callable, Optional, Set

import dbus
from dbus.mainloop.glib import DBusGMainLoop

# Initialize D-Bus GLib main loop integration
DBusGMainLoop(set_as_default=True)

# Configuration Constants
LIKES_FILE = os.path.expanduser("~/.config/spotify_likes.json")
HIDDEN_FILE = os.path.expanduser("~/.config/spotify_hidden.json")


@dataclass(frozen=True)
class TrackMetadata:
    """Immutable data transfer object representing current track info."""
    title: str = "Titre inconnu"
    artist: str = "Artiste inconnu"
    album: str = "Album inconnu"
    art_url: str = ""
    uri: str = ""
    is_valid: bool = False


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


def setup_mpris_observer(
    on_metadata_changed: Optional[Callable[[], None]] = None,
    player: Optional[MPRISPlayerFacade] = None,
    on_playback_status: Optional[Callable[[], None]] = None
):
    """Subscribes to D-Bus PropertiesChanged events to notify subscribers immediately."""
    if player is None:
        player = MPRISPlayerFacade()

    def on_properties_changed(interface_name, changed_properties, _invalidated):
        if interface_name == "org.mpris.MediaPlayer2.Player":
            if "Metadata" in changed_properties and on_metadata_changed:
                on_metadata_changed()
            if "PlaybackStatus" in changed_properties:
                if on_playback_status:
                    on_playback_status()
                else:
                    try:
                        subprocess.run(["pkill", "-RTMIN+11", "waybar"], stderr=subprocess.DEVNULL)
                    except Exception:
                        pass

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
