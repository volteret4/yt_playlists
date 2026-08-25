"""'¿Ya la tengo?' a nivel de canción: biblioteca local primero (sin red),
Airsonic de fallback. Mismo orden de fuentes que usa el enriquecimiento de
lastfm_explorer para álbumes (biblioteca local -> red), aplicado aquí a
canciones sueltas."""
import os

from airsonic_client import search_song, AirsonicError
from db import get_musica_local_conn
from normalize import normalize

AIRSONIC_URL = os.environ.get("AIRSONIC_URL", "")
AIRSONIC_USER = os.environ.get("AIRSONIC_USER", "")
AIRSONIC_PASS = os.environ.get("AIRSONIC_PASS", "")


def _load_local_index() -> set:
    """Set de 'artista_norm|titulo_norm' de toda la biblioteca local."""
    index = set()
    try:
        conn = get_musica_local_conn()
    except Exception:
        return index
    try:
        rows = conn.execute("SELECT artist, title FROM songs").fetchall()
        for r in rows:
            index.add(f"{normalize(r['artist'])}|{normalize(r['title'])}")
    except Exception:
        pass
    finally:
        conn.close()
    return index


def check_local(artist: str, title: str, local_index: set) -> bool:
    if not artist or not title:
        return False
    return f"{normalize(artist)}|{normalize(title)}" in local_index


def check_airsonic(artist: str, title: str) -> bool:
    if not AIRSONIC_URL or not artist or not title:
        return False
    try:
        results = search_song(AIRSONIC_URL, AIRSONIC_USER, AIRSONIC_PASS, f"{artist} {title}")
    except (AirsonicError, Exception):
        return False
    target_artist, target_title = normalize(artist), normalize(title)
    for r in results:
        if normalize(r["artist"]) == target_artist and normalize(r["title"]) == target_title:
            return True
    return False


def check_ownership(artist: str, title: str, local_index: set) -> tuple[bool, str | None]:
    """Devuelve (owned, source)."""
    if check_local(artist, title, local_index):
        return True, "musica_local"
    if check_airsonic(artist, title):
        return True, "airsonic"
    return False, None
