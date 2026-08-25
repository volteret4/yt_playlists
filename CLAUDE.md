# yt_playlists

## Arquitectura

- `youtube_client.py` — YouTube Data API v3 vía `requests` (sin
  `google-api-python-client`, sin `yt-dlp` a propósito — ver README).
- `parse_title.py` — heurística artista/canción, sin dependencias externas.
- `airsonic_client.py` — mismo patrón `_call()` con reintentos de
  versión/auth que `services/artist-sync/clients/airsonic_client.py`, pero
  con `search_song()` (canciones sueltas) en vez de `list_artists()`.
- `ownership.py` — biblioteca local (`musica_local.sqlite`, sin red)
  primero, Airsonic de fallback. `_load_local_index()` carga toda la
  biblioteca una vez por ejecución de `sync.py`, no por canción.
- `sync.py` — orquestación (`add_user`, `add_playlist`, `sync_playlist`,
  `sync_all`) y CLI para el job diario de Ofelia.
- `server.py` — Flask, una plantilla HTML con JS vanilla (mismo patrón que
  el resto de servicios del monorepo).
- `db.py` — `yt_playlists.db` propia (users/playlists/tracks) +
  conexión de solo lectura a `musica_local.sqlite` con `immutable=1` en la
  URI (bind-mount `:ro` de Docker — `mode=ro` solo no basta, mismo problema
  ya encontrado y documentado en `services/lastfm_explorer/db.py`).
- `enrich_info.py` — info para el panel lateral (Last.fm + Wikipedia +
  MusicBrainz), mismo patrón que `services/escuchowsky/app_discover.py`
  (`lfm_get`/`_lfm_image`/`mb_search_release_group`, reutilizados casi tal
  cual). Como aquí solo se tiene artista+canción (no álbum), primero mira
  `musica_local.sqlite` para el álbum si la canción es propia; si no, usa
  `track.getInfo` de Last.fm para resolverlo antes de pedir
  `album.getInfo`. `wikipedia_summary()` es nuevo (no existía en
  escuchowsky) — REST API pública de Wikipedia, sin API key.

## Por qué no yt-dlp

`services/tracklist/` (mismo servidor) ya se ha encontrado con "Sign in to
confirm you're not a bot" de YouTube al hacer scraping desde la IP del
servidor. La API oficial con `YOUTUBE_API_KEY` no tiene ese problema y ya
está provisionada en el repo (la usa `escuchowsky`).

## Por qué no qBittorrent para "¿ya la tengo?"

El título de una canción casi nunca es substring del nombre de un torrent
(sí lo es un álbum completo) — a diferencia de
`services/dieta_sonora/airsonic_clean_csv.py`/`qbittorrent_cleaner_csv.py`
(que sí comparan contra nombres de torrent, pero a nivel de álbum), aquí
solo se usa biblioteca local + Airsonic.
