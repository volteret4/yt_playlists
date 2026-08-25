"""Heurística de parseo artista/canción a partir del título de un vídeo de
YouTube + el nombre del canal que lo subió. No hay edición manual en v1 --
el título crudo se enseña siempre en la UI para que se note cuándo el
parseo es dudoso.
"""
import re

_JUNK_RE = re.compile(
    r"[\(\[][^\)\]]*?(official|video|audio|lyric|lyrics|hd|4k|visualizer|"
    r"music video|explicit|clean|remaster\w*|full album|album version)"
    r"[^\)\]]*?[\)\]]",
    re.IGNORECASE,
)
_SEPARATORS = (" - ", " – ", " — ")


def clean_title(title: str) -> str:
    cleaned = _JUNK_RE.sub("", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—")
    return cleaned or title.strip()


def parse_title(raw_title: str, channel_title: str = "") -> tuple[str | None, str]:
    """Devuelve (artista, cancion). artista puede ser None si no se pudo inferir."""
    raw_title = (raw_title or "").strip()
    channel_title = (channel_title or "").strip()

    if channel_title.endswith(" - Topic"):
        artist = channel_title[: -len(" - Topic")].strip()
        return artist or None, clean_title(raw_title)

    cleaned = clean_title(raw_title)
    for sep in _SEPARATORS:
        if sep in cleaned:
            left, right = cleaned.split(sep, 1)
            left, right = left.strip(), right.strip()
            if left and right:
                return left, right

    return (channel_title or None), cleaned
