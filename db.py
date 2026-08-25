import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/app/yt_playlists.db")
MUSICA_LOCAL_DB = os.environ.get("MUSICA_LOCAL_DB", "/musica_local.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    channel_id    TEXT UNIQUE NOT NULL,
    channel_title TEXT NOT NULL,
    handle        TEXT,
    added_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS playlists (
    id             INTEGER PRIMARY KEY,
    playlist_id    TEXT UNIQUE NOT NULL,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    title          TEXT NOT NULL,
    item_count     INTEGER,
    last_synced_at TEXT
);
CREATE TABLE IF NOT EXISTS tracks (
    id            INTEGER PRIMARY KEY,
    playlist_id   INTEGER NOT NULL REFERENCES playlists(id),
    video_id      TEXT NOT NULL,
    position      INTEGER,
    raw_title     TEXT NOT NULL,
    parsed_artist TEXT,
    parsed_title  TEXT,
    owned         INTEGER,
    owned_source  TEXT,
    checked_at    TEXT,
    UNIQUE(playlist_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_tracks_playlist ON tracks(playlist_id);
CREATE INDEX IF NOT EXISTS idx_playlists_user ON playlists(user_id);
"""


def init_db(path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_musica_local_conn() -> sqlite3.Connection:
    # immutable=1 -- musica_local.sqlite se monta :ro en Docker; mode=ro
    # solo no basta en un bind-mount de solo lectura (ver
    # services/lastfm_explorer/db.py, mismo problema encontrado ahí).
    conn = sqlite3.connect(f"file:{MUSICA_LOCAL_DB}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
