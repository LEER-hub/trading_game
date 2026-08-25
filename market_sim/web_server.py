from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import urlparse

from .live_engine import LiveMarketEngine


WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


class TradingRequestHandler(BaseHTTPRequestHandler):
    engine: LiveMarketEngine

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {self.address_string()} {format % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            return self._json(self.engine.snapshot())
        if path == "/api/stream":
            return self._stream()
        routes = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        if path not in routes:
            return self.send_error(HTTPStatus.NOT_FOUND)
        filename, content_type = routes[path]
        body = (WEB_ROOT / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/order":
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16_384:
                raise ValueError("Request too large")
            payload = json.loads(self.rfile.read(length))
            trade = self.engine.place_order(str(payload["symbol"]), str(payload["side"]), float(payload["quantity"]))
            self._json({"ok": True, "trade": trade, "portfolio": self.engine.snapshot()})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _stream(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_version = -1
        try:
            while True:
                snapshot = self.engine.snapshot()
                if snapshot["version"] != last_version:
                    payload = json.dumps(snapshot, separators=(",", ":"))
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_version = snapshot["version"]
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    engine = LiveMarketEngine()
    TradingRequestHandler.engine = engine
    server = ThreadingHTTPServer((host, port), TradingRequestHandler)
    engine.start()
    print(f"Mercury Markets running at http://{host}:{port}")
    print(f"Mode: {'Twelve Data anchored' if engine.provider.enabled else 'SIMULATION (set TWELVE_DATA_API_KEY for external anchors)'}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.shutdown()
        engine.stop()
        server.server_close()
