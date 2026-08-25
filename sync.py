#!/usr/bin/env python3
"""Sincronización: añadir usuarios/playlists y refrescar sus canciones +
comprobación de 'ya la tengo'.

Uso:
    python3 sync.py --all                  # resincroniza todo lo seguido
    python3 sync.py --playlist <id_interno>  # resincroniza una sola playlist
"""
import argparse
from datetime import datetime, timezone

import youtube_client as yt
from db import get_conn
from ownership import _load_local_index, check_ownership
from parse_title import parse_title

_SKIP_TITLES = {"Private video", "Deleted video"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_user(handle_or_url: str) -> int:
    info = yt.resolve_channel(handle_or_url)
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (channel_id, channel_title, handle, added_at) VALUES (?,?,?,?) "
        "ON CONFLICT(channel_id) DO UPDATE SET channel_title=excluded.channel_title, handle=excluded.handle",
        (info["channel_id"], info["channel_title"], info["handle"], _now()),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE channel_id = ?", (info["channel_id"],)).fetchone()["id"]

    for pl in yt.list_playlists(info["channel_id"]):
        conn.execute(
            "INSERT INTO playlists (playlist_id, user_id, title, item_count) VALUES (?,?,?,?) "
            "ON CONFLICT(playlist_id) DO UPDATE SET title=excluded.title, item_count=excluded.item_count",
            (pl["playlist_id"], user_id, pl["title"], pl["item_count"]),
        )
    conn.commit()
    conn.close()
    return user_id


def add_playlist(playlist_url_or_id: str) -> int:
    playlist_id = yt.extract_playlist_id(playlist_url_or_id)
    meta = yt.get_playlist_meta(playlist_id)

    conn = get_conn()
    user_row = conn.execute("SELECT id FROM users WHERE channel_id = ?", (meta["channel_id"],)).fetchone()
    if user_row:
        user_id = user_row["id"]
    else:
        conn.execute(
            "INSERT INTO users (channel_id, channel_title, handle, added_at) VALUES (?,?,?,?)",
            (meta["channel_id"], meta["channel_title"], None, _now()),
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE channel_id = ?", (meta["channel_id"],)).fetchone()["id"]

    conn.execute(
        "INSERT INTO playlists (playlist_id, user_id, title, item_count) VALUES (?,?,?,?) "
        "ON CONFLICT(playlist_id) DO UPDATE SET title=excluded.title, item_count=excluded.item_count",
        (meta["playlist_id"], user_id, meta["title"], meta["item_count"]),
    )
    conn.commit()
    playlist_row_id = conn.execute(
        "SELECT id FROM playlists WHERE playlist_id = ?", (meta["playlist_id"],)
    ).fetchone()["id"]
    conn.close()
    return playlist_row_id


def sync_playlist(playlist_row_id: int, local_index: set | None = None) -> None:
    if local_index is None:
        local_index = _load_local_index()

    conn = get_conn()
    row = conn.execute("SELECT playlist_id FROM playlists WHERE id = ?", (playlist_row_id,)).fetchone()
    if not row:
        conn.close()
        return
    playlist_id = row["playlist_id"]

    items = yt.list_playlist_items(playlist_id)
    for item in items:
        if item["raw_title"] in _SKIP_TITLES or not item["video_id"]:
            continue
        artist, title = parse_title(item["raw_title"], item["channel_title"])
        owned, source = check_ownership(artist, title, local_index)
        conn.execute(
            """
            INSERT INTO tracks (playlist_id, video_id, position, raw_title, parsed_artist, parsed_title, owned, owned_source, checked_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(playlist_id, video_id) DO UPDATE SET
                position=excluded.position, raw_title=excluded.raw_title,
                parsed_artist=excluded.parsed_artist, parsed_title=excluded.parsed_title,
                owned=excluded.owned, owned_source=excluded.owned_source, checked_at=excluded.checked_at
            """,
            (playlist_row_id, item["video_id"], item["position"], item["raw_title"],
             artist, title, int(owned), source, _now()),
        )

    conn.execute(
        "UPDATE playlists SET item_count = ?, last_synced_at = ? WHERE id = ?",
        (len(items), _now(), playlist_row_id),
    )
    conn.commit()
    conn.close()


def sync_all() -> None:
    local_index = _load_local_index()
    conn = get_conn()
    playlist_ids = [r["id"] for r in conn.execute("SELECT id FROM playlists")]
    conn.close()
    print(f"Resincronizando {len(playlist_ids)} playlists...")
    for pid in playlist_ids:
        try:
            sync_playlist(pid, local_index)
        except Exception as e:
            print(f"  fallo en playlist {pid}: {e}")
    print("Hecho.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--playlist", type=int, help="id interno de la playlist a resincronizar")
    args = parser.parse_args()

    if args.all:
        sync_all()
    else:
        sync_playlist(args.playlist)
