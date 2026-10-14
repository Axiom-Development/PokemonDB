#!/usr/bin/env python3
"""PokemonDB local server: stdlib http.server + SQLite + a buildless
HTML/CSS/JS frontend. Binds to 127.0.0.1 only -- see README for the local
deployment limits this implies (no TLS, no multi-host access, a simple
global lock serializes writes instead of a connection pool).

Run with:  python server.py [port]
"""

import json
import mimetypes
import os
import sys
import threading
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import api
from app import bodyparse
from app.data import DATASET
from app.db import Store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
DEFAULT_PORT = 8800

STORE_LOCK = threading.Lock()
STORE = Store()

STATIC_ROOTS = {
    "": WEB_DIR,       # /styles/..., /scripts/..., /fonts/...
    "images": IMAGES_DIR,
}


def safe_join(root, rel_path):
    rel_path = rel_path.lstrip("/")
    full = os.path.normpath(os.path.join(root, rel_path))
    if not full.startswith(os.path.normpath(root)):
        return None
    return full


class Handler(BaseHTTPRequestHandler):
    server_version = "PokemonDB/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- helpers ----

    def _session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = cookies.SimpleCookie()
        jar.load(raw)
        morsel = jar.get(api.SESSION_COOKIE)
        return morsel.value if morsel else None

    def _current_user(self):
        token = self._session_token()
        if not token:
            return None
        with STORE_LOCK:
            return STORE.get_session_user(token)

    def _read_json_body(self):
        length = bodyparse.parse_content_length(self.headers.get("Content-Length"))
        if length is None:
            return None
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return bodyparse.parse_json_object(raw)

    def _send_json(self, status, payload, set_token=None, clear_cookie=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if set_token:
            self.send_header(
                "Set-Cookie",
                f"{api.SESSION_COOKIE}={set_token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={60*60*24*14}",
            )
        if clear_cookie:
            self.send_header(
                "Set-Cookie",
                f"{api.SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0",
            )
        self.end_headers()
        self.wfile.write(body)

    def _handle_api(self, method):
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        json_body = self._read_json_body()
        if json_body is None:
            self._send_json(400, {"error": "Malformed JSON body."})
            return

        user = self._current_user()
        token = self._session_token()
        status, payload, new_token = api.dispatch(
            method, parts.path, query, json_body, STORE_wrapped(), DATASET, user, session_token=token
        )
        if new_token == "":
            self._send_json(status, payload, clear_cookie=True)
        elif new_token:
            self._send_json(status, payload, set_token=new_token)
        else:
            self._send_json(status, payload)

    def _serve_static(self):
        parts = urlsplit(self.path)
        path = parts.path
        if path == "/":
            path = "/index.html"

        top = path.split("/", 2)[1] if path.count("/") >= 1 else ""
        if top == "images":
            root = IMAGES_DIR
            rel = path[len("/images/"):]
        else:
            root = WEB_DIR
            rel = path

        full = safe_join(root, rel)
        if full is None or not os.path.isfile(full):
            self._send_json(404, {"error": "Not found."})
            return

        ctype, _ = mimetypes.guess_type(full)
        ctype = ctype or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"

        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if full.endswith(".woff2"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._handle_api("GET")
        else:
            self._serve_static()

    def do_POST(self):
        self._handle_api("POST")

    def do_PUT(self):
        self._handle_api("PUT")

    def do_DELETE(self):
        self._handle_api("DELETE")


class LockedStoreProxy:
    """Serializes all SQLite access behind STORE_LOCK; a local single-user
    dev tool has no need for a connection pool, and sqlite3 itself is not
    thread-safe across connections without this."""

    def __init__(self, store, lock):
        self._store = store
        self._lock = lock

    def __getattr__(self, name):
        attr = getattr(self._store, name)
        if not callable(attr):
            return attr

        def wrapped(*args, **kwargs):
            with self._lock:
                return attr(*args, **kwargs)
        return wrapped


def STORE_wrapped():
    return LockedStoreProxy(STORE, STORE_LOCK)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    host = "127.0.0.1"
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"PokemonDB running at http://{host}:{port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
