#!/usr/bin/env python3
"""
HTTP SSE Event Broadcaster & Spicetify Bridge for Spotify Card.
Manages Server-Sent Events subscribers and HTTP API callbacks.

Design Patterns:
- Observer / Publisher-Subscriber: SSENotifier broadcasts events to clients.
- Handler: BridgeHTTPHandler handles REST and SSE streaming requests.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from typing import Callable, Optional

from spotify_mpris import TrackRepository

SSE_PORT = 8975


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
    on_track_update: Optional[Callable[[], None]] = None
    on_like_update: Optional[Callable[[str, bool], None]] = None

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

    server = ThreadingHTTPServer(("127.0.0.1", port), BridgeHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server
