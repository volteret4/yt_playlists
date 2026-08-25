"""Cliente YouTube Data API v3 -- solo lectura, vía requests directos (mismo
patrón ligero que services/escuchowsky/app_discover.py, sin
google-api-python-client). Necesita YOUTUBE_API_KEY (misma que ya usa
escuchowsky, provisionada vía sops).

Se evita deliberadamente yt-dlp para listar canales/playlists: este mismo
servidor ya se ha encontrado con el bloqueo "Sign in to confirm you're not a
bot" de YouTube al scrapear desde su IP (ver services/tracklist/README.md).
La API oficial no tiene ese problema.
"""
import os
import re

import requests

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
BASE = "https://www.googleapis.com/youtube/v3"

_CHANNEL_ID_RE = re.compile(r"(?:channel/)?(UC[\w-]{22})")
_HANDLE_RE = re.compile(r"@([\w.-]+)")
_PLAYLIST_ID_RE = re.compile(r"[?&]list=([\w-]+)")


class YouTubeError(Exception):
    pass


def _get(endpoint: str, **params) -> dict:
    params["key"] = API_KEY
    resp = requests.get(f"{BASE}/{endpoint}", params=params, timeout=15)
    if not resp.ok:
        raise YouTubeError(f"{endpoint} -> HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _paginate(endpoint: str, **params):
    page_token = None
    while True:
        p = dict(params)
        if page_token:
            p["pageToken"] = page_token
        data = _get(endpoint, **p)
        yield from data.get("items", [])
        page_token = data.get("nextPageToken")
        if not page_token:
            break


def extract_channel_id(raw: str) -> str | None:
    m = _CHANNEL_ID_RE.search(raw)
    return m.group(1) if m else None


def extract_handle(raw: str) -> str | None:
    m = _HANDLE_RE.search(raw)
    if m:
        return m.group(1)
    if raw.strip() and "/" not in raw and "." not in raw:
        return raw.strip().lstrip("@")
    return None


def extract_playlist_id(raw: str) -> str:
    m = _PLAYLIST_ID_RE.search(raw)
    if m:
        return m.group(1)
    return raw.strip()


def resolve_channel(handle_or_url_or_id: str) -> dict:
    """Devuelve {channel_id, channel_title, handle}."""
    raw = handle_or_url_or_id.strip()
    channel_id = extract_channel_id(raw)
    if channel_id:
        data = _get("channels", part="snippet", id=channel_id)
    else:
        handle = extract_handle(raw)
        if not handle:
            raise YouTubeError(f"No se pudo interpretar como canal: {raw}")
        data = _get("channels", part="snippet", forHandle=f"@{handle}")

    items = data.get("items", [])
    if not items:
        raise YouTubeError(f"No se encontró el canal: {raw}")
    ch = items[0]
    snippet = ch["snippet"]
    return {
        "channel_id": ch["id"],
        "channel_title": snippet["title"],
        "handle": snippet.get("customUrl"),
    }


def resolve_channel_by_id(channel_id: str) -> dict:
    data = _get("channels", part="snippet", id=channel_id)
    items = data.get("items", [])
    if not items:
        raise YouTubeError(f"No se encontró el canal: {channel_id}")
    ch = items[0]
    snippet = ch["snippet"]
    return {"channel_id": ch["id"], "channel_title": snippet["title"], "handle": snippet.get("customUrl")}


def list_playlists(channel_id: str) -> list[dict]:
    out = []
    for item in _paginate("playlists", part="snippet,contentDetails", channelId=channel_id, maxResults=50):
        out.append({
            "playlist_id": item["id"],
            "title": item["snippet"]["title"],
            "item_count": item.get("contentDetails", {}).get("itemCount", 0),
        })
    return out


def get_playlist_meta(playlist_id: str) -> dict:
    data = _get("playlists", part="snippet,contentDetails", id=playlist_id)
    items = data.get("items", [])
    if not items:
        raise YouTubeError(f"No se encontró la playlist: {playlist_id}")
    pl = items[0]
    snippet = pl["snippet"]
    return {
        "playlist_id": pl["id"],
        "title": snippet["title"],
        "item_count": pl.get("contentDetails", {}).get("itemCount", 0),
        "channel_id": snippet["channelId"],
        "channel_title": snippet["channelTitle"],
    }


def list_playlist_items(playlist_id: str) -> list[dict]:
    out = []
    for item in _paginate("playlistItems", part="snippet,contentDetails", playlistId=playlist_id, maxResults=50):
        snippet = item["snippet"]
        resource = snippet.get("resourceId", {})
        if resource.get("kind") != "youtube#video":
            continue
        out.append({
            "video_id": resource.get("videoId") or item.get("contentDetails", {}).get("videoId"),
            "position": snippet.get("position"),
            "raw_title": snippet.get("title", ""),
            "channel_title": snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle") or "",
        })
    return out
