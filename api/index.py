"""Vercel serverless entry point: every /api/* request is rewritten here
(see vercel.json) and handed to the same dispatcher the local server uses.

Storage is Postgres when DATABASE_URL is set (required on Vercel); without
it this falls back to the local SQLite file, which is handy for testing the
handler on a laptop.
"""

import json
import os
import sys
from http import cookies
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import api, bodyparse  # noqa: E402
from app.data import DATASET  # noqa: E402

_STORE = None


def get_store():
    global _STORE
    if _STORE is None:
        dsn = os.environ.get("DATABASE_URL")
        if dsn:
            from app.db_pg import PgStore
            _STORE = PgStore(dsn)
        else:
            from app.db import Store
            _STORE = Store(os.path.join(os.environ.get("TMPDIR", "/tmp"), "pokemondb.sqlite3"))
    return _STORE


class handler(BaseHTTPRequestHandler):
    server_version = "PokemonDB-Vercel/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

    # -- request parsing --------------------------------------------------
    def _route(self):
        """The rewrite passes the original API path as ?p=...; fall back to
        the raw path if the platform preserved it instead."""
        parts = urlsplit(self.path)
        query = parse_qs(parts.query, keep_blank_values=True)
        original = query.pop("p", [None])[0]
        path = original or parts.path
        if not path.startswith("/"):
            path = "/" + path
        if path.startswith("/api/index"):
            path = "/api/meta"
        return path, query

    def _session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = cookies.SimpleCookie()
        try:
            jar.load(raw)
        except cookies.CookieError:
            return None
        morsel = jar.get(api.SESSION_COOKIE)
        return morsel.value if morsel else None

    def _read_json_body(self):
        length = bodyparse.parse_content_length(self.headers.get("Content-Length"))
        if length is None:
            return None
        if length == 0:
            return {}
        return bodyparse.parse_json_object(self.rfile.read(length))

    # -- response ---------------------------------------------------------
    def _send_json(self, status, payload, set_token=None, clear_cookie=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Vercel terminates TLS and sets X-Forwarded-Proto; plain-HTTP local
        # runs must not mark the cookie Secure or browsers would drop it.
        proto = self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
        flags = "Path=/; HttpOnly; SameSite=Strict" + ("; Secure" if proto == "https" else "")
        if set_token:
            self.send_header(
                "Set-Cookie", f"{api.SESSION_COOKIE}={set_token}; {flags}; Max-Age={60 * 60 * 24 * 14}"
            )
        if clear_cookie:
            self.send_header("Set-Cookie", f"{api.SESSION_COOKIE}=; {flags}; Max-Age=0")
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, method):
        try:
            path, query = self._route()
            json_body = self._read_json_body()
            if json_body is None:
                self._send_json(400, {"error": "Malformed JSON body."})
                return
            store = get_store()
            token = self._session_token()
            user = store.get_session_user(token) if token else None
            status, payload, new_token = api.dispatch(
                method, path, query, json_body, store, DATASET, user, session_token=token
            )
            if new_token == "":
                self._send_json(status, payload, clear_cookie=True)
            elif new_token:
                self._send_json(status, payload, set_token=new_token)
            else:
                self._send_json(status, payload)
        except Exception as exc:  # never leak internals; log for Vercel's runtime logs
            sys.stderr.write(f"unhandled error: {type(exc).__name__}: {exc}\n")
            self._send_json(500, {"error": "Server error."})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")
