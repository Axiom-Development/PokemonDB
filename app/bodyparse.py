"""Pure helpers for reading a JSON object out of an HTTP request body.

Kept separate from server.py (which owns the live SQLite connection) so
these can be unit tested directly without spinning up the HTTP server.
"""

import json

MAX_BODY_BYTES = 1_000_000  # generous for this app's small JSON payloads


def parse_content_length(header_value, max_bytes=MAX_BODY_BYTES):
    """Returns the number of body bytes to read, or None if the header is
    missing-but-malformed, negative, non-numeric, or exceeds max_bytes --
    any of which means the request should be rejected rather than read."""
    if header_value is None:
        return 0
    try:
        length = int(header_value)
    except (TypeError, ValueError):
        return None
    if length < 0 or length > max_bytes:
        return None
    return length


def parse_json_object(raw_bytes):
    """Parses raw_bytes as JSON, returning a dict on success, or None if
    the bytes are not valid UTF-8, not valid JSON, or valid JSON that
    isn't an object (e.g. a bare list, string, number, or null)."""
    if not raw_bytes:
        return {}
    try:
        parsed = json.loads(raw_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None
