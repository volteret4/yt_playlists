# yt_playlists

Web para seguir usuarios de YouTube, ver sus playlists y comprobar qué
canciones de cada una ya tienes en tu colección local. Parte de
[repeat-one](https://github.com/volteret4/repeat-one).

## Cómo funciona

- **Listar canales/playlists/canciones**: YouTube Data API v3
  (`YOUTUBE_API_KEY`, misma variable que ya usa `escuchowsky`), vía
  `requests` directos — deliberadamente sin `yt-dlp`: este mismo servidor ya
  se ha encontrado con el bloqueo "Sign in to confirm you're not a bot" de
  YouTube al scrapear desde su IP.
- **Parseo artista/canción**: heurística sobre el título del vídeo +
  nombre del canal (`parse_title.py`) — detecta canales "- Topic"
  (auto-generados por artista) y si no, separa por " - "/" – "/" — "
  limpiando sufijos típicos ("(Official Video)", etc). Sin edición manual
  en v1; el título original siempre se enseña en la UI.
- **"¿Ya la tengo?"**: primero `musica_local.sqlite` (biblioteca de
  music-fuzzy, mismo archivo que usa `lastfm_explorer` y
  `sellos-discograficos`, sin red), luego Airsonic (`search3`) de fallback.
  Resultado cacheado por canción — no se repite hasta que se resincroniza
  esa playlist.
- **Panel lateral** (`enrich_info.py`): al hacer click en una canción se
  abre un panel flotante a la derecha con el embed de YouTube, info de
  artista (Last.fm) + Wikipedia + enlaces MusicBrainz, e info del álbum
  (biblioteca local si la canción es propia, si no `track.getInfo` de
  Last.fm para resolver el álbum y luego `album.getInfo`). Mismo patrón que
  `services/escuchowsky/app_discover.py` (`lfm_get`/`_lfm_image`/
  `mb_search_release_group`), con Wikipedia añadido.

## Variables de entorno

```bash
YOUTUBE_API_KEY=...
AIRSONIC_URL=...
AIRSONIC_USER=...
AIRSONIC_PASS=...
LASTFM_API_KEY=...
DB_PATH=/app/yt_playlists.db
MUSICA_LOCAL_DB=/musica_local.sqlite
PORT=5000
```

## Uso

```bash
pip install -r requirements.txt
python3 sync.py --all      # resincroniza todo lo seguido (job diario en producción)
python3 server.py          # web en 0.0.0.0:5000
```

Añadir usuarios/playlists sueltas se hace desde la propia web (formularios
arriba de la lista), que llaman a `sync.add_user()`/`sync.add_playlist()`.
