"""SQLite persistence for accounts, sessions, collections and teams.

Only mutable, per-user state lives here. Pokemon reference data stays in
app.data (loaded from the read-only CSV). The database file is created in
the project-local runtime/ folder, which is gitignored.
"""

import os
import sqlite3
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
DB_PATH = os.path.join(RUNTIME_DIR, "pokemondb.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    username_lower TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS collection (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pokedex_number INTEGER NOT NULL,
    added_at REAL NOT NULL,
    PRIMARY KEY (user_id, pokedex_number)
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'manual',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS team_members (
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    pokedex_number INTEGER NOT NULL,
    PRIMARY KEY (team_id, slot)
);
"""


def connect(db_path=DB_PATH):
    dirname = os.path.dirname(db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


class Store:
    def __init__(self, db_path=DB_PATH):
        self.conn = connect(db_path)

    # ---- users ----
    def create_user(self, username, salt_hex, password_hash_hex):
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO users (username, username_lower, salt, password_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, username.lower(), salt_hex, password_hash_hex, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_user_by_username(self, username):
        row = self.conn.execute(
            "SELECT * FROM users WHERE username_lower = ?", (username.lower(),)
        ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id):
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    # ---- sessions ----
    def create_session(self, token, user_id, expires_at):
        now = time.time()
        self.conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, expires_at),
        )
        self.conn.commit()

    def get_session_user(self, token):
        row = self.conn.execute(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token = ? AND sessions.expires_at > ?",
            (token, time.time()),
        ).fetchone()
        return dict(row) if row else None

    def delete_session(self, token):
        self.conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        self.conn.commit()

    # ---- collection ----
    def get_collection(self, user_id):
        rows = self.conn.execute(
            "SELECT pokedex_number FROM collection WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ).fetchall()
        return [r["pokedex_number"] for r in rows]

    def add_to_collection(self, user_id, pokedex_number):
        self.conn.execute(
            "INSERT OR IGNORE INTO collection (user_id, pokedex_number, added_at) VALUES (?, ?, ?)",
            (user_id, pokedex_number, time.time()),
        )
        self.conn.commit()

    def remove_from_collection(self, user_id, pokedex_number):
        self.conn.execute(
            "DELETE FROM collection WHERE user_id = ? AND pokedex_number = ?",
            (user_id, pokedex_number),
        )
        self.conn.commit()

    # ---- teams ----
    def list_teams(self, user_id):
        rows = self.conn.execute(
            "SELECT * FROM teams WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
        ).fetchall()
        teams = []
        for row in rows:
            team = dict(row)
            team["members"] = self._team_members(team["id"])
            teams.append(team)
        return teams

    def get_team(self, user_id, team_id):
        row = self.conn.execute(
            "SELECT * FROM teams WHERE user_id = ? AND id = ?", (user_id, team_id)
        ).fetchone()
        if row is None:
            return None
        team = dict(row)
        team["members"] = self._team_members(team_id)
        return team

    def _team_members(self, team_id):
        rows = self.conn.execute(
            "SELECT slot, pokedex_number FROM team_members WHERE team_id = ? ORDER BY slot",
            (team_id,),
        ).fetchall()
        return [r["pokedex_number"] for r in rows]

    def create_team(self, user_id, name, mode, members):
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO teams (user_id, name, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, mode, now, now),
        )
        team_id = cur.lastrowid
        self._set_team_members(team_id, members)
        self.conn.commit()
        return team_id

    def update_team(self, user_id, team_id, name=None, mode=None, members=None):
        existing = self.get_team(user_id, team_id)
        if existing is None:
            return None
        name = existing["name"] if name is None else name
        mode = existing["mode"] if mode is None else mode
        self.conn.execute(
            "UPDATE teams SET name = ?, mode = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (name, mode, time.time(), team_id, user_id),
        )
        if members is not None:
            self._set_team_members(team_id, members)
        self.conn.commit()
        return self.get_team(user_id, team_id)

    def _set_team_members(self, team_id, members):
        self.conn.execute("DELETE FROM team_members WHERE team_id = ?", (team_id,))
        for slot, pokedex_number in enumerate(members):
            self.conn.execute(
                "INSERT INTO team_members (team_id, slot, pokedex_number) VALUES (?, ?, ?)",
                (team_id, slot, pokedex_number),
            )

    def delete_team(self, user_id, team_id):
        cur = self.conn.execute(
            "DELETE FROM teams WHERE id = ? AND user_id = ?", (team_id, user_id)
        )
        self.conn.commit()
        return cur.rowcount > 0
