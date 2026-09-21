#!/usr/bin/env python3
"""
Lightweight MPRIS helper script for Waybar Spotify controls.
Refactored using Facade and Command patterns with fail-safe D-Bus timeouts.
"""
from abc import ABC, abstractmethod
import json
import sys
import dbus

JSON_STOPPED = '{"text": "", "class": "stopped"}\n'
JSON_PREV = '{"text": "", "tooltip": "Piste précédente", "class": "spotify-btn"}\n'
JSON_NEXT = '{"text": "", "tooltip": "Piste suivante", "class": "spotify-btn"}\n'
JSON_PLAYING = '{"text": "", "tooltip": "Mettre en pause", "class": "playing"}\n'
JSON_PAUSED = '{"text": "", "tooltip": "Reprendre la lecture", "class": "paused"}\n'


class SpotifyMPRISClient:
    """Facade isolating MPRIS D-Bus calls with low latency and fail-safes."""

    def __init__(self):
        self._bus = None
        self._props = None
        self._status = None

    def _connect(self):
        if self._props is None:
            self._bus = dbus.SessionBus()
            player = self._bus.get_object(
                'org.mpris.MediaPlayer2.spotify',
                '/org/mpris/MediaPlayer2',
                introspect=False
            )
            self._props = dbus.Interface(player, 'org.freedesktop.DBus.Properties')

    def get_playback_status(self) -> str:
        if self._status is not None:
            return self._status
        try:
            self._connect()
            self._status = str(self._props.Get(
                'org.mpris.MediaPlayer2.Player',
                'PlaybackStatus',
                timeout=0.08
            ))
            return self._status
        except Exception:
            self._status = ""
            return ""

    def get_progress_data(self):
        try:
            self._connect()
            status = self.get_playback_status()
            if not status:
                return None
            pos_us = self._props.Get('org.mpris.MediaPlayer2.Player', 'Position', timeout=0.08)
            meta = self._props.Get('org.mpris.MediaPlayer2.Player', 'Metadata', timeout=0.08)
            len_us = meta.get('mpris:length', 0)
            return status, float(pos_us) / 1000000.0, float(len_us) / 1000000.0
        except Exception:
            return None


class ICommand(ABC):
    """Command interface for Waybar MPRIS queries."""

    @abstractmethod
    def execute(self, client: SpotifyMPRISClient) -> str:
        pass


class PrevCommand(ICommand):
    def execute(self, client: SpotifyMPRISClient) -> str:
        return JSON_PREV if client.get_playback_status() else JSON_STOPPED


class NextCommand(ICommand):
    def execute(self, client: SpotifyMPRISClient) -> str:
        return JSON_NEXT if client.get_playback_status() else JSON_STOPPED


class PlayPauseCommand(ICommand):
    def execute(self, client: SpotifyMPRISClient) -> str:
        status = client.get_playback_status()
        if not status:
            return JSON_STOPPED
        return JSON_PLAYING if status == 'Playing' else JSON_PAUSED


class ProgressCommand(ICommand):
    def execute(self, client: SpotifyMPRISClient) -> str:
        data = client.get_progress_data()
        if not data:
            return JSON_STOPPED
        status, pos_s, len_s = data
        if len_s <= 0:
            return '{"text": "", "class": "empty"}\n'

        pct = min(1.0, max(0.0, pos_s / len_s))
        bar_len = 8
        filled = int(round(pct * bar_len))
        played = "━" * filled
        unplayed = "━" * (bar_len - filled)

        pos_min, pos_sec = int(pos_s // 60), int(pos_s % 60)
        len_min, len_sec = int(len_s // 60), int(len_s % 60)
        pos_str = f"{pos_min}:{pos_sec:02d}"
        len_str = f"{len_min}:{len_sec:02d}"

        theme_color = "#00f0ff" if status == "Playing" else "#718096"
        bar_html = f"<span color='{theme_color}'>{played}</span><span color='#334155'>{unplayed}</span>"
        text = f"{pos_str} {bar_html} {len_str}"
        tooltip = f"Progression : {pos_str} / {len_str} ({int(pct*100)}%)\nMolette : Avancer / Reculer (5s)"
        cls = "playing" if status == "Playing" else "paused"

        return json.dumps({"text": text, "tooltip": tooltip, "class": cls}, ensure_ascii=False) + "\n"


class CommandDispatcher:
    """Dispatcher registry mapping CLI flags to concrete commands."""

    def __init__(self):
        self._commands = {
            '--prev': PrevCommand(),
            '--next': NextCommand(),
            '--play-pause': PlayPauseCommand(),
            '--progress': ProgressCommand(),
        }

    def dispatch(self, flag: str, client: SpotifyMPRISClient) -> str:
        cmd = self._commands.get(flag, self._commands['--progress'])
        return cmd.execute(client)


def main():
    flag = sys.argv[1] if len(sys.argv) > 1 else '--progress'
    client = SpotifyMPRISClient()
    dispatcher = CommandDispatcher()
    sys.stdout.write(dispatcher.dispatch(flag, client))


if __name__ == '__main__':
    main()
