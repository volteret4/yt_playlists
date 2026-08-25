"""Cliente Subsonic API para Airsonic -- mismo patrón que
services/artist-sync/clients/airsonic_client.py (_call() con reintentos
automáticos de versión/auth), con una función nueva para buscar canciones
sueltas que ese cliente no tiene (solo lista artistas)."""
import hashlib
import secrets

import requests


class AirsonicError(Exception):
    pass


def _params(user, password, version, use_token=True, **extra):
    base = {"u": user, "v": version, "c": "yt-playlists", "f": "json"}
    if use_token:
        salt = secrets.token_hex(8)
        token = hashlib.md5((password + salt).encode()).hexdigest()
        base.update({"t": token, "s": salt})
    else:
        base["p"] = password
    return {**base, **extra}


def _raw_call(base_url, user, password, version, endpoint, use_token=True, **kwargs):
    url = f"{base_url}/rest/{endpoint}.view"
    resp = requests.get(url, params=_params(user, password, version, use_token, **kwargs), timeout=15)
    resp.raise_for_status()
    return resp.json().get("subsonic-response", {})


def _call(base_url, user, password, version, endpoint, **kwargs):
    use_token = True
    data = _raw_call(base_url, user, password, version, endpoint, use_token, **kwargs)

    if data.get("status") != "ok":
        err = data.get("error", {})

        if err.get("code") == 30:
            server_version = data.get("version")
            if server_version and server_version != version:
                version = server_version
                data = _raw_call(base_url, user, password, version, endpoint, use_token, **kwargs)
                err = data.get("error", {}) if data.get("status") != "ok" else {}

        if data.get("status") != "ok" and "non-hashed" in (err.get("message") or "").lower():
            use_token = False
            data = _raw_call(base_url, user, password, version, endpoint, use_token, **kwargs)

        if data.get("status") != "ok":
            err = data.get("error", {})
            raise AirsonicError(err.get("message", "Unknown Airsonic error"))

    return data


def search_song(base_url, user, password, query, version="1.15.0") -> list[dict]:
    """Busca canciones por texto libre (título/artista). Devuelve
    [{title, artist, album}, ...] -- solo lo necesario para comparar."""
    data = _call(base_url, user, password, version, "search3", query=query, songCount=20, artistCount=0, albumCount=0)
    songs = data.get("searchResult3", {}).get("song", [])
    return [{"title": s.get("title", ""), "artist": s.get("artist", ""), "album": s.get("album", "")} for s in songs]
