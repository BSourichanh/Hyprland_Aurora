#!/usr/bin/env python3
"""
HTTP SSE Event Broadcaster & Spicetify Bridge for Spotify Card.
Manages Server-Sent Events subscribers with disconnect detection,
bounded POST payloads, and local CORS restriction.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import select
import socket
import threading
import time
from typing import Callable, Optional

from spotify_mpris import TrackRepository

SSE_PORT = 8975
MAX_POST_BYTES = 65536
ALLOWED_ORIGIN_RE = re.compile(
    r"^(https?://(127\.0\.0\.1|localhost)(:\d+)?|https://(xpui\.app|open)\.spotify\.com)$"
)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class SSENotifier:
    """Thread-safe manager for active Server-Sent Events subscribers."""

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

    def send_keepalive(self, wfile) -> bool:
        with self._lock:
            if wfile not in self._clients:
                return False
            try:
                wfile.write(b": keepalive\n\n")
                wfile.flush()
                return True
            except Exception:
                self._clients.remove(wfile)
                return False

    def broadcast(self, action: str, **extra):
        payload = {"action": action, **extra}
        msg = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
        with self._lock:
            dead = []
            for w in self._clients:
                try:
                    w.write(msg)
                    w.flush()
                except Exception:
                    dead.append(w)
            for w in dead:
                if w in self._clients:
                    self._clients.remove(w)


class BridgeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP & SSE bridge connecting Spicetify extensions to the desktop daemon."""
    notifier: Optional[SSENotifier] = None
    repo: Optional[TrackRepository] = None
    on_track_update: Optional[Callable[[], None]] = None
    on_like_update: Optional[Callable[[str, bool], None]] = None

    def log_message(self, format, *args):
        return

    def _send_cors_headers(self):
        origin = self.headers.get("Origin", "").strip()
        if origin and ALLOWED_ORIGIN_RE.match(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        else:
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")

    def _is_client_disconnected(self) -> bool:
        try:
            rlist, _, _ = select.select([self.connection], [], [], 1.0)
            if self.connection in rlist:
                peek = self.connection.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                if not peek:
                    return True
        except (OSError, ValueError):
            return True
        return False

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._send_cors_headers()
            self.end_headers()
            if self.notifier:
                self.notifier.add_client(self.wfile)
            last_ping = time.monotonic()
            try:
                while True:
                    if self._is_client_disconnected():
                        break
                    now = time.monotonic()
                    if now - last_ping >= 15.0:
                        last_ping = now
                        if self.notifier and not self.notifier.send_keepalive(self.wfile):
                            break
            except Exception:
                pass
            finally:
                if self.notifier:
                    self.notifier.remove_client(self.wfile)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/status":
            raw_len = self.headers.get("Content-Length", "0")
            try:
                content_len = int(raw_len)
            except ValueError:
                self.send_response(400)
                self.end_headers()
                return
            if content_len < 0 or content_len > MAX_POST_BYTES:
                self.send_response(413 if content_len > MAX_POST_BYTES else 400)
                self.end_headers()
                return

            body = self.rfile.read(content_len).decode("utf-8", errors="replace") if content_len else "{}"
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("JSON object expected")
                uri = data.get("uri")
                liked = bool(data.get("liked", False))
                if uri and self.repo:
                    self.repo.set_liked(str(uri), liked)
                    if self.on_like_update:
                        self.on_like_update(str(uri), liked)
            except (json.JSONDecodeError, ValueError, TypeError):
                self.send_response(400)
                self._send_cors_headers()
                self.end_headers()
                return

            self.send_response(200)
            self._send_cors_headers()
            self.end_headers()
            try:
                self.wfile.write(b'{"status":"ok"}')
            except OSError:
                pass
        elif self.path == "/songchange":
            if self.on_track_update:
                self.on_track_update()
            self.send_response(200)
            self._send_cors_headers()
            self.end_headers()
            try:
                self.wfile.write(b'{"status":"ok"}')
            except OSError:
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def start_sse_server(
    port: int = SSE_PORT,
    notifier: Optional[SSENotifier] = None,
    repo: Optional[TrackRepository] = None,
    on_track_update: Optional[Callable[[], None]] = None,
    on_like_update: Optional[Callable[[str, bool], None]] = None
) -> ThreadingHTTPServer:
    """Configures and launches the HTTP/SSE daemon server in a background thread."""
    BridgeHTTPHandler.notifier = notifier
    BridgeHTTPHandler.repo = repo
    BridgeHTTPHandler.on_track_update = on_track_update
    BridgeHTTPHandler.on_like_update = on_like_update

    server = ReusableThreadingHTTPServer(("127.0.0.1", port), BridgeHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server