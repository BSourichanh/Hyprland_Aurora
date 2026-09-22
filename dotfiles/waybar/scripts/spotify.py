#!/usr/bin/env python3
"""
Lightweight MPRIS helper script for Waybar Spotify controls.
Refactored using Facade and Command patterns with fail-safe D-Bus timeouts.
"""
from abc import ABC, abstractmethod
import json
import sys
import time
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

    def reset(self):
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

    def get_playback_status(self, fresh: bool = False) -> str:
        if not fresh and self._status is not None:
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
            self.reset()
            self._status = ""
            return ""

    def get_progress_data(self):
        try:
            self._connect()
            status = self.get_playback_status(fresh=True)
            if not status:
                return None
            pos_us = self._props.Get('org.mpris.MediaPlayer2.Player', 'Position', timeout=0.08)
            meta = self._props.Get('org.mpris.MediaPlayer2.Player', 'Metadata', timeout=0.08)
            len_us = meta.get('mpris:length', 0)
            return status, float(pos_us) / 1000000.0, float(len_us) / 1000000.0
        except Exception:
            self.reset()
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
    """Streaming progress bar with fine, constant-width animated equalizer."""

    BAR_FRAMES = [
        " ▃▅ ",
        "▂▅▇▃",
        "▃▇▅▅",
        "▅▅▃▇",
        "▇▃ ▅",
        "▅ ▂▃",
        "▃▂▄ ",
        " ▄▆▂",
    ]
    BAR_PAUSED = " ▂▂ "

    def execute(self, client: SpotifyMPRISClient) -> str:
        frame_idx = 0
        last_state = None

        while True:
            try:
                data = client.get_progress_data()
                if not data:
                    if last_state != "stopped":
                        sys.stdout.write(JSON_STOPPED)
                        sys.stdout.flush()
                        last_state = "stopped"
                    time.sleep(1.5)
                    continue

                status, pos_s, len_s = data
                if len_s <= 0:
                    if last_state != "empty":
                        sys.stdout.write('{"text": "", "class": "empty"}\n')
                        sys.stdout.flush()
                        last_state = "empty"
                    time.sleep(1.5)
                    continue

                pct = min(1.0, max(0.0, pos_s / len_s))
                bar_len = 8
                filled = int(round(pct * bar_len))
                played = "━" * filled
                unplayed = "━" * (bar_len - filled)

                pos_min, pos_sec = int(pos_s // 60), int(pos_s % 60)
                len_min, len_sec = int(len_s // 60), int(len_s % 60)
                pos_str = f"{pos_min:02d}:{pos_sec:02d}"
                len_str = f"{len_min:02d}:{len_sec:02d}"

                if status == "Playing":
                    bars = self.BAR_FRAMES[frame_idx % len(self.BAR_FRAMES)]
                    frame_idx += 1
                    theme_color = "#00f0ff"
                    cls = "playing"
                else:
                    bars = self.BAR_PAUSED
                    theme_color = "#7aa2f7"
                    cls = "paused"

                bars_html = f"<span font_family='Noto Sans Mono' font_size='9pt' color='{theme_color}'>{bars}</span>"
                bar_html = f"<span color='{theme_color}'>{played}</span><span color='#334155'>{unplayed}</span>"
                text = f"{bars_html}  {pos_str} {bar_html} {len_str}"
                tooltip = f"Progression : {pos_str} / {len_str} ({int(pct*100)}%)\nClic gauche : Carte déroulante\nClic droit : Lecture / Pause\nMolette : Avancer / Reculer (5s)"

                sys.stdout.write(json.dumps({"text": text, "tooltip": tooltip, "class": cls}, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                last_state = cls

                time.sleep(0.25 if status == "Playing" else 0.5)

            except (KeyboardInterrupt, SystemExit):
                break
            except Exception:
                client.reset()
                time.sleep(1.0)

        return ""


class BarsCommand(ICommand):
    """Streaming animated equalizer bars for Spotify mini-player."""

    FRAMES = [
        " ▃▅ ",
        "▂▅▇▃",
        "▃▇▅▅",
        "▅▅▃▇",
        "▇▃ ▅",
        "▅ ▂▃",
        "▃▂▄ ",
        " ▄▆▂",
    ]

    def execute(self, client: SpotifyMPRISClient) -> str:
        frame_idx = 0
        last_state = None

        while True:
            try:
                status = client.get_playback_status(fresh=True)
                if not status:
                    if last_state != "stopped":
                        sys.stdout.write(JSON_STOPPED)
                        sys.stdout.flush()
                        last_state = "stopped"
                    time.sleep(1.5)
                    continue

                if status == "Playing":
                    frame = self.FRAMES[frame_idx % len(self.FRAMES)]
                    frame_idx += 1
                    text = f"<span color='#00f0ff'>{frame}</span>"
                    tooltip = "Spotify : Lecture en cours\nClic gauche : Carte déroulante\nClic droit : Lecture / Pause"
                    data = {"text": text, "tooltip": tooltip, "class": "playing"}
                    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
                    last_state = "playing"
                    time.sleep(0.2)
                elif status == "Paused":
                    if last_state != "paused":
                        text = "<span color='#7aa2f7'> ▂▂ </span>"
                        tooltip = "Spotify : En pause\nClic gauche : Carte déroulante\nClic droit : Reprendre"
                        data = {"text": text, "tooltip": tooltip, "class": "paused"}
                        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
                        sys.stdout.flush()
                        last_state = "paused"
                    time.sleep(0.5)
                else:
                    if last_state != "stopped":
                        sys.stdout.write(JSON_STOPPED)
                        sys.stdout.flush()
                        last_state = "stopped"
                    time.sleep(1.5)
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception:
                client.reset()
                time.sleep(1.0)
        return ""


class CommandDispatcher:
    """Dispatcher registry mapping CLI flags to concrete commands."""

    def __init__(self):
        self._commands = {
            '--prev': PrevCommand(),
            '--next': NextCommand(),
            '--play-pause': PlayPauseCommand(),
            '--progress': ProgressCommand(),
            '--bars': BarsCommand(),
        }

    def dispatch(self, flag: str, client: SpotifyMPRISClient) -> str:
        cmd = self._commands.get(flag, self._commands['--progress'])
        return cmd.execute(client)


def main():
    flag = sys.argv[1] if len(sys.argv) > 1 else '--progress'
    client = SpotifyMPRISClient()
    dispatcher = CommandDispatcher()
    res = dispatcher.dispatch(flag, client)
    if res:
        sys.stdout.write(res)


if __name__ == '__main__':
    main()
