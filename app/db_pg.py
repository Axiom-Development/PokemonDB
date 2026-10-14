"""Postgres persistence for accounts, sessions, collections and teams.

Same public interface as app.db.Store (so app.api is untouched); used when
DATABASE_URL is set, e.g. on Vercel where the filesystem is read-only and
ephemeral. Pokemon reference data still comes from the read-only CSV.

Serverless-friendly: one cached connection per warm instance, transparently
re-opened if the pooler dropped it, and no server-side prepared statements
(prepare_threshold=None) so it works behind Supabase's transaction pooler.
"""

import time

import psycopg
from psycopg.rows import dict_row

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        username_lower TEXT NOT NULL UNIQUE,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at DOUBLE PRECISION NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at DOUBLE PRECISION NOT NULL,
        expires_at DOUBLE PRECISION NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS collection (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        pokedex_number INTEGER NOT NULL,
        added_at DOUBLE PRECISION NOT NULL,
        PRIMARY KEY (user_id, pokedex_number)
    )""",
    """CREATE TABLE IF NOT EXISTS teams (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'manual',
        created_at DOUBLE PRECISION NOT NULL,
        updated_at DOUBLE PRECISION NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS team_members (
        team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
        slot INTEGER NOT NULL,
        pokedex_number INTEGER NOT NULL,
        PRIMARY KEY (team_id, slot)
    )""",
    "CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions (expires_at)",
    "CREATE INDEX IF NOT EXISTS teams_user_idx ON teams (user_id, updated_at DESC)",
]

_RETRY_ERRORS = (psycopg.OperationalError, psycopg.InterfaceError)


class PgStore:
    def __init__(self, dsn):
        self.dsn = dsn
        self._conn = None
        for statement in SCHEMA:
            self._run(statement)

    # ---- connection handling ----
    def _connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(
                self.dsn, row_factory=dict_row, autocommit=True, prepare_threshold=None
            )
        return self._conn

    def _run(self, sql, params=(), fetch=None):
        """fetch: None | 'one' | 'all'. Retries once on a dropped connection."""
        for attempt in (0, 1):
            try:
                with self._connection().cursor() as cur:
                    cur.execute(sql, params)
                    if fetch == "one":
                        return cur.fetchone()
                    if fetch == "all":
                        return cur.fetchall()
                    return cur.rowcount
            except _RETRY_ERRORS:
                self._conn = None
                if attempt == 1:
                    raise

    # ---- users ----
    def create_user(self, username, salt_hex, password_hash_hex):
        row = self._run(
            "INSERT INTO users (username, username_lower, salt, password_hash, created_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (username, username.lower(), salt_hex, password_hash_hex, time.time()),
            fetch="one",
        )
        return row["id"]

    def get_user_by_username(self, username):
        return self._run(
            "SELECT * FROM users WHERE username_lower = %s", (username.lower(),), fetch="one"
        )

    def get_user_by_id(self, user_id):
        return self._run("SELECT * FROM users WHERE id = %s", (user_id,), fetch="one")

    # ---- sessions ----
    def create_session(self, token, user_id, expires_at):
        self._run(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
            (token, user_id, time.time(), expires_at),
        )

    def get_session_user(self, token):
        return self._run(
            "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token = %s AND sessions.expires_at > %s",
            (token, time.time()),
            fetch="one",
        )

    def delete_session(self, token):
        self._run("DELETE FROM sessions WHERE token = %s", (token,))

    # ---- collection ----
    def get_collection(self, user_id):
        rows = self._run(
            "SELECT pokedex_number FROM collection WHERE user_id = %s ORDER BY added_at",
            (user_id,),
            fetch="all",
        )
        return [r["pokedex_number"] for r in rows]

    def add_to_collection(self, user_id, pokedex_number):
        self._run(
            "INSERT INTO collection (user_id, pokedex_number, added_at) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (user_id, pokedex_number, time.time()),
        )

    def remove_from_collection(self, user_id, pokedex_number):
        self._run(
            "DELETE FROM collection WHERE user_id = %s AND pokedex_number = %s",
            (user_id, pokedex_number),
        )

    # ---- teams ----
    def list_teams(self, user_id):
        rows = self._run(
            "SELECT * FROM teams WHERE user_id = %s ORDER BY updated_at DESC",
            (user_id,),
            fetch="all",
        )
        teams = []
        for row in rows:
            team = dict(row)
            team["members"] = self._team_members(team["id"])
            teams.append(team)
        return teams

    def get_team(self, user_id, team_id):
        row = self._run(
            "SELECT * FROM teams WHERE user_id = %s AND id = %s", (user_id, team_id), fetch="one"
        )
        if row is None:
            return None
        team = dict(row)
        team["members"] = self._team_members(team_id)
        return team

    def _team_members(self, team_id):
        rows = self._run(
            "SELECT slot, pokedex_number FROM team_members WHERE team_id = %s ORDER BY slot",
            (team_id,),
            fetch="all",
        )
        return [r["pokedex_number"] for r in rows]

    def _set_team_members(self, cur, team_id, members):
        cur.execute("DELETE FROM team_members WHERE team_id = %s", (team_id,))
        for slot, pokedex_number in enumerate(members):
            cur.execute(
                "INSERT INTO team_members (team_id, slot, pokedex_number) VALUES (%s, %s, %s)",
                (team_id, slot, pokedex_number),
            )

    def create_team(self, user_id, name, mode, members):
        now = time.time()
        conn = self._connection()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO teams (user_id, name, mode, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (user_id, name, mode, now, now),
                )
                team_id = cur.fetchone()["id"]
                self._set_team_members(cur, team_id, members)
        return team_id

    def update_team(self, user_id, team_id, name=None, mode=None, members=None):
        existing = self.get_team(user_id, team_id)
        if existing is None:
            return None
        name = existing["name"] if name is None else name
        mode = existing["mode"] if mode is None else mode
        conn = self._connection()
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE teams SET name = %s, mode = %s, updated_at = %s "
                    "WHERE id = %s AND user_id = %s",
                    (name, mode, time.time(), team_id, user_id),
                )
                if members is not None:
                    self._set_team_members(cur, team_id, members)
        return self.get_team(user_id, team_id)

    def delete_team(self, user_id, team_id):
        return self._run("DELETE FROM teams WHERE id = %s AND user_id = %s", (team_id, user_id)) > 0
