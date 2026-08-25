"""Info de artista/álbum para el panel lateral: Last.fm + Wikipedia +
MusicBrainz. Mismo patrón que services/escuchowsky/app_discover.py
(lfm_get/_lfm_image/mb_search_release_group) -- se reutiliza esa forma en
vez de reinventar una nueva, con Wikipedia añadido (no existía ahí) y
resolución álbum-a-partir-de-canción (aquí solo tenemos artista+canción, no
el álbum, a diferencia de escuchowsky que ya opera a nivel de álbum)."""
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from db import get_musica_local_conn
from normalize import normalize

LFM_API_KEY = os.environ.get("LASTFM_API_KEY") or None
CAA = "https://coverartarchive.org/release-group"
_LFM_NO_IMG = "2a96cbd8b46e442fc41c2b86b821562f"
_UA = "yt-playlists/1.0 (https://github.com/volteret4/yt_playlists)"


def _lfm_image(images: list, size: str = "extralarge") -> str:
    for img in images:
        url = img.get("#text", "")
        if img.get("size") == size and url and _LFM_NO_IMG not in url:
            return url
    return ""


def lfm_get(method: str, params: dict) -> dict:
    if not LFM_API_KEY:
        return {"error": "sin LASTFM_API_KEY"}
    base = "https://ws.audioscrobbler.com/2.0/"
    params = {**params, "method": method, "api_key": LFM_API_KEY, "format": "json"}
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}


def mb_search_artist(artist: str) -> dict:
    q = f'artist:"{artist}"'
    url = "https://musicbrainz.org/ws/2/artist?" + urllib.parse.urlencode({"query": q, "fmt": "json", "limit": "1"})
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        results = data.get("artists", [])
        if results:
            return {"mbid": results[0].get("id", ""), "name": results[0].get("name", artist)}
    except Exception:
        pass
    return {}


def mb_search_release_group(artist: str, album: str) -> dict:
    q = f'artist:"{artist}" AND release:"{album}"'
    url = "https://musicbrainz.org/ws/2/release-group?" + urllib.parse.urlencode({"query": q, "fmt": "json", "limit": "1"})
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        rgs = data.get("release-groups", [])
        if rgs:
            rg = rgs[0]
            return {"mbid": rg.get("id", ""), "title": rg.get("title", album), "date": rg.get("first-release-date", "")}
    except Exception:
        pass
    return {}


def wikipedia_summary(title: str, lang: str = "en") -> dict:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        if data.get("type") == "disambiguation":
            return {}
        return {
            "extract": data.get("extract", ""),
            "url": (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
            "thumbnail": (data.get("thumbnail") or {}).get("source", ""),
        }
    except Exception:
        return {}


def _local_album(artist: str, title: str) -> dict:
    """Si la canción está en musica_local.sqlite, su álbum/sello/año/género
    reales -- más fiables que cualquier fuente externa."""
    try:
        conn = get_musica_local_conn()
    except Exception:
        return {}
    try:
        target = f"{normalize(artist)}|{normalize(title)}"
        for r in conn.execute("SELECT artist, title, album, label, year, genre FROM songs"):
            if f"{normalize(r['artist'])}|{normalize(r['title'])}" == target:
                return {"album": r["album"], "label": r["label"], "year": r["year"], "genre": r["genre"]}
    except Exception:
        pass
    finally:
        conn.close()
    return {}


def get_track_info(artist: str, title: str) -> dict:
    result = {"artist": {}, "album": {}, "wikipedia": {}, "musicbrainz": {}}
    if not artist:
        return result

    # ── Artista: Last.fm ────────────────────────────────────────────────
    ar_data = lfm_get("artist.getInfo", {"artist": artist, "autocorrect": 1})
    if "artist" in ar_data:
        ar = ar_data["artist"]
        result["artist"] = {
            "name": ar.get("name", artist),
            "bio": (ar.get("bio", {}).get("summary", "") or "").split("<a ")[0].strip(),
            "listeners": ar.get("stats", {}).get("listeners", ""),
            "image": _lfm_image(ar.get("image", [])),
            "url": ar.get("url", ""),
            "tags": [t["name"] for t in (ar.get("tags", {}).get("tag", []) or [])[:6]],
        }
    time.sleep(0.15 + random.random() * 0.15)

    # ── Álbum: biblioteca local primero, si no Last.fm track.getInfo ──────
    local = _local_album(artist, title)
    album_name = local.get("album")
    if not album_name:
        tr_data = lfm_get("track.getInfo", {"artist": artist, "track": title, "autocorrect": 1})
        album_name = (tr_data.get("track", {}) or {}).get("album", {}).get("title")

    if album_name:
        time.sleep(0.15 + random.random() * 0.15)
        al_data = lfm_get("album.getInfo", {"artist": artist, "album": album_name, "autocorrect": 1})
        if "album" in al_data:
            al = al_data["album"]
            result["album"] = {
                "name": al.get("name", album_name),
                "wiki": (al.get("wiki", {}).get("summary", "") or "").split("<a ")[0].strip(),
                "image": _lfm_image(al.get("image", [])),
                "url": al.get("url", ""),
                "tags": [t["name"] for t in (al.get("tags", {}).get("tag", []) or [])[:6]],
            }
        else:
            result["album"] = {"name": album_name}
        result["album"].update({k: v for k, v in local.items() if k != "album" and v})

        mb_rg = mb_search_release_group(artist, album_name)
        if mb_rg.get("mbid"):
            result["musicbrainz"]["release_group_mbid"] = mb_rg["mbid"]
            result["musicbrainz"]["release_group_url"] = f"https://musicbrainz.org/release-group/{mb_rg['mbid']}"
            if not result["album"].get("image"):
                result["album"]["image"] = f"{CAA}/{mb_rg['mbid']}/front-500"
            if not result["album"].get("year") and mb_rg.get("date"):
                result["album"]["year"] = mb_rg["date"][:4]

    # ── MusicBrainz artista + Wikipedia ──────────────────────────────────
    time.sleep(0.15 + random.random() * 0.15)
    mb_artist = mb_search_artist(artist)
    if mb_artist.get("mbid"):
        result["musicbrainz"]["artist_mbid"] = mb_artist["mbid"]
        result["musicbrainz"]["artist_url"] = f"https://musicbrainz.org/artist/{mb_artist['mbid']}"

    wiki = wikipedia_summary(artist)
    if wiki:
        result["wikipedia"] = wiki

    return result
