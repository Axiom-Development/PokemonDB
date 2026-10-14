"""Password hashing and session token helpers.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib hashlib), each with a
unique random salt (stdlib secrets), per OWASP guidance for when a
dedicated password-hashing library isn't available. Session tokens are
opaque random strings stored server-side in SQLite with an expiry; the
client only ever holds the token itself (in an HttpOnly cookie).
"""

import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16
SESSION_TOKEN_BYTES = 32
SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 14  # 14 days


def hash_password(password, salt=None):
    """Returns (salt_hex, hash_hex) for a new or existing salt."""
    if salt is None:
        salt = secrets.token_bytes(SALT_BYTES)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, expected_hash_hex):
    _, computed_hash_hex = hash_password(password, salt_hex)
    return hmac.compare_digest(computed_hash_hex, expected_hash_hex)


def new_session_token():
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


USERNAME_MIN = 3
USERNAME_MAX = 24
PASSWORD_MIN = 8


def validate_username(username):
    if not isinstance(username, str):
        return "Username is required."
    username = username.strip()
    if not (USERNAME_MIN <= len(username) <= USERNAME_MAX):
        return f"Username must be {USERNAME_MIN}-{USERNAME_MAX} characters."
    if not all(c.isalnum() or c in "_-" for c in username):
        return "Username may only contain letters, numbers, - and _."
    return None


def validate_password(password):
    if not isinstance(password, str):
        return "Password is required."
    if len(password) < PASSWORD_MIN:
        return f"Password must be at least {PASSWORD_MIN} characters."
    return None
