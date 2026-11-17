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

## Instalación con Docker Compose

```bash
cp .env.example .env
```

Rellena `.env` (credenciales y carpetas de tu equipo) y arranca:

```bash
docker compose up -d --build
```

Los datos que genera (bases, cachés) se quedan en esta misma carpeta, fuera de git.

## Actualizaciones automáticas

El `docker-compose.yml` trae su propia [Ofelia](https://github.com/mcuadros/ofelia), que lanza dentro del contenedor los mismos trabajos y a las mismas horas que en REPEAT-ONE (formato con segundos: `seg min hora día mes día-semana`, hora de `TZ`, por defecto Europe/Madrid):

| Trabajo | Cuándo | Qué lanza |
|---|---|---|
| `yt-playlists-daily` | `0 20 0 * * *` | `python3 sync.py --all` |

Para cambiar una hora, edita su etiqueta `ofelia.job-exec.<trabajo>.schedule` en `docker-compose.yml` y vuelve a hacer `docker compose up -d`. Para lanzarlo a mano: `docker compose exec <servicio> <orden>`. Para no tener actualizaciones automáticas: `docker compose stop ofelia`.

Esta Ofelia solo ve los contenedores de este repo (etiqueta `repeat-one.ofelia`), así que puedes tener varios módulos instalados por separado sin que se pisen. Necesita el socket de Docker en solo lectura.
